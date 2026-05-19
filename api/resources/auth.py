import re
import secrets
from flask import request, make_response
from flask_restful import Resource
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_csrf_token,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.models.user import User
from api.models.user_identity import UserIdentity
from api.common.energy import ensure_referral_code, apply_referral_code
from api.common.oauth import OAuthError, VERIFIERS


def _csrf_payload(access_token=None, refresh_token=None):
    csrf = {}
    if access_token:
        csrf["access"] = get_csrf_token(access_token)
    if refresh_token:
        csrf["refresh"] = get_csrf_token(refresh_token)
    return {"csrf": csrf} if csrf else {}


def _issue_cookies(user_id, message, status=200):
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)
    body = {"message": message, **_csrf_payload(access_token, refresh_token)}
    resp = make_response(body, status)
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp


class LoginResource(Resource):
    decorators = [limiter.limit("10 per minute")]

    def post(self):
        data = request.get_json(silent=True) or {}
        email = data.get("email") or data.get("username")
        password = data.get("password")

        if not email or not password:
            return {"error": "email (or username) and password required"}, 400

        user = db.session.execute(
            db.select(User).where((User.email == email) | (User.name == email))
        ).scalar_one_or_none()

        if user is None or not user.check_password(password):
            return {"error": "Invalid credentials"}, 401

        return _issue_cookies(user.id, "Logged in")


class RefreshResource(Resource):
    decorators = [jwt_required(refresh=True), limiter.limit("20 per minute")]

    def post(self):
        access_token = create_access_token(identity=get_jwt_identity())
        body = {"message": "Token refreshed", **_csrf_payload(access_token)}
        resp = make_response(body, 200)
        set_access_cookies(resp, access_token)
        return resp


class GuestLoginResource(Resource):
    decorators = [limiter.limit("20 per minute")]

    def post(self):
        from api.resources.me import normalize_language
        data = request.get_json(silent=True) or {}
        language = normalize_language(data.get("language")) or normalize_language(
            (request.headers.get("Accept-Language") or "").split(",")[0]
        )
        guest = User(
            name=f"guest_{secrets.token_hex(8)}",
            is_guest=True,
            language=language,
        )
        ensure_referral_code(guest)
        ok, error = apply_referral_code(guest, data.get("referral_code"))
        if not ok:
            return {"error": error}, 400
        db.session.add(guest)
        db.session.commit()
        return _issue_cookies(guest.id, "Guest session created", status=201)


class LogoutResource(Resource):
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def delete(self):
        resp = make_response({"message": "Logged out"}, 200)
        unset_jwt_cookies(resp)
        return resp


# --- OAuth sign-in ------------------------------------------------------

_USERNAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]")


def _generate_username(email: str | None) -> str:
    base = "user"
    if email:
        local = email.split("@", 1)[0]
        cleaned = _USERNAME_SAFE.sub("", local)[:32]
        if cleaned:
            base = cleaned
    return f"{base}_{secrets.token_hex(4)}"


def _attach_identity(user: User, provider: str, claims: dict) -> UserIdentity:
    identity = UserIdentity(
        user_id=user.id,
        provider=provider,
        subject=claims["sub"],
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified")),
    )
    db.session.add(identity)
    return identity


def _optional_current_user() -> User | None:
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    uid = get_jwt_identity()
    if not uid:
        return None
    return db.session.get(User, uid)


def _read_token(data: dict) -> str | None:
    return data.get("id_token") or data.get("credential")


def _oauth_sign_in(provider: str):
    data = request.get_json(silent=True) or {}
    token = _read_token(data)
    if not token:
        return {"error": "id_token required"}, 400

    try:
        claims = VERIFIERS[provider](token)
    except OAuthError as exc:
        return {"error": exc.message}, exc.status

    identity = db.session.execute(
        db.select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.subject == claims["sub"],
        )
    ).scalar_one_or_none()

    if identity is not None:
        return _issue_cookies(identity.user_id, "Logged in")

    current_user = _optional_current_user()
    email = claims.get("email")
    email_verified = bool(claims.get("email_verified"))

    if current_user is not None:
        # Authenticated caller — attach to their account (covers guest upgrade
        # and "I'm signed in already, now add Google too").
        target = current_user
        if target.is_guest:
            target.is_guest = False
            if email_verified and email and not target.email:
                target.email = email
    elif email and email_verified:
        target = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if target is None:
            target = User(
                name=_generate_username(email),
                email=email,
                is_guest=False,
            )
            ensure_referral_code(target)
            db.session.add(target)
    else:
        # No verified email: never auto-link by email. If an account already
        # claims this address, force the user to sign in with their existing
        # method first and link from settings.
        if email:
            exists = db.session.execute(
                db.select(User.id).where(User.email == email)
            ).scalar_one_or_none()
            if exists is not None:
                return {
                    "error": "An account with this email already exists. Sign in with your existing method, then link this provider from settings.",
                    "code": "account_exists",
                }, 409
        target = User(
            name=_generate_username(email),
            email=None,
            is_guest=False,
        )
        ensure_referral_code(target)
        db.session.add(target)

    db.session.flush()
    _attach_identity(target, provider, claims)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"error": "Account conflict — try signing in instead"}, 409

    return _issue_cookies(target.id, "Logged in")


class GoogleAuthResource(Resource):
    decorators = [limiter.limit("20 per minute")]

    def post(self):
        return _oauth_sign_in("google")


class IdentityLinkResource(Resource):
    """Attach or remove an OAuth identity on the authenticated user."""
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def post(self, provider):
        if provider not in VERIFIERS:
            return {"error": "Unsupported provider"}, 400
        data = request.get_json(silent=True) or {}
        token = _read_token(data)
        if not token:
            return {"error": "id_token required"}, 400
        try:
            claims = VERIFIERS[provider](token)
        except OAuthError as exc:
            return {"error": exc.message}, exc.status

        uid = get_jwt_identity()
        existing = db.session.execute(
            db.select(UserIdentity).where(
                UserIdentity.provider == provider,
                UserIdentity.subject == claims["sub"],
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.user_id == uid:
                return {"message": "Already linked"}, 200
            return {"error": "This identity is already linked to another account"}, 409

        user = db.session.get(User, uid)
        if user is None:
            return {"error": "User not found"}, 404
        _attach_identity(user, provider, claims)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Identity could not be linked"}, 409
        return {"message": "Linked"}, 201

    def delete(self, provider):
        if provider not in VERIFIERS:
            return {"error": "Unsupported provider"}, 400
        uid = get_jwt_identity()
        identity = db.session.execute(
            db.select(UserIdentity).where(
                UserIdentity.provider == provider,
                UserIdentity.user_id == uid,
            )
        ).scalar_one_or_none()
        if identity is None:
            return {"error": "Not linked"}, 404

        user = db.session.get(User, uid)
        remaining = db.session.execute(
            db.select(db.func.count(UserIdentity.id)).where(
                UserIdentity.user_id == uid,
                UserIdentity.id != identity.id,
            )
        ).scalar() or 0
        if remaining == 0 and not user.password_hash:
            return {"error": "Cannot remove your only sign-in method. Set a password first."}, 409

        db.session.delete(identity)
        db.session.commit()
        return {"message": "Unlinked"}, 200
