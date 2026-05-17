from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from api import db, limiter
from api.models.user import User
from api.models.friendship import Friendship, PENDING, ACCEPTED
from api.common.energy import get_energy, get_energy_boost, award_claim_bonus
from api.common.base_model import utc_isoformat
from api.common.limits import ENERGY_DAILY_GUEST, ENERGY_DAILY_USER, ENERGY_MAX_SUBSCRIBER
from api.resources.subscriptions import _active_subscription, _serialize as _serialize_sub
from api.common.subscription_plans import (
    DEFAULT_CURRENCY,
    STATUS_ACTIVE,
    STATUS_CANCELLED,
    SUPPORTED_CURRENCIES,
    normalize_currency,
)

SUPPORTED_LANGUAGES = {"en", "es", "fr", "de", "nl", "pt"}


def normalize_language(code):
    if not code:
        return None
    lower = str(code).lower().split("-")[0]
    return lower if lower in SUPPORTED_LANGUAGES else None


def _current_user() -> User:
    user = db.session.get(User, get_jwt_identity())
    if user is None:
        abort(401)
    return user


class MeResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        user = _current_user()
        return _serialize_user(user), 200

    def put(self):
        return self._update()

    def patch(self):
        return self._update()

    def _update(self):
        user = _current_user()
        data = request.get_json(silent=True) or {}
        if "name" in data:
            user.name = data["name"]
        if "email" in data:
            user.email = data["email"]
        if "password" in data:
            user.set_password(data["password"])
        if "currency" in data:
            currency = normalize_currency(data["currency"])
            if currency is None:
                return {"error": f"Invalid currency. Choose from: {', '.join(sorted(SUPPORTED_CURRENCIES))}"}, 400
            user.currency = currency
        if "language" in data:
            language = normalize_language(data["language"])
            if language is None:
                return {"error": f"Invalid language. Choose from: {', '.join(sorted(SUPPORTED_LANGUAGES))}"}, 400
            user.language = language
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Username or email already taken"}, 409
        return _serialize_user(user), 200

    def delete(self):
        user = _current_user()
        db.session.delete(user)
        db.session.commit()
        return {}, 204


class ClaimResource(Resource):
    """Convert a guest account into a full account in-place."""
    decorators = [jwt_required(), limiter.limit("5 per minute")]

    def post(self):
        user = _current_user()
        if not user.is_guest:
            return {"error": "Account already claimed"}, 409

        data = request.get_json(silent=True) or {}
        missing = [f for f in ("email", "password") if not data.get(f)]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400

        user.email = data["email"]
        user.set_password(data["password"])
        if data.get("name"):
            user.name = data["name"]
        award_claim_bonus(user)
        user.is_guest = False
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Email or username already taken"}, 409

        return _serialize_user(user), 200


class FriendListResource(Resource):
    """GET /me/friends — accepted friends; POST — send invite by email."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        rows = db.session.execute(
            db.select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.addressee),
            )
            .where(
                Friendship.status == ACCEPTED,
                or_(Friendship.requester_id == uid, Friendship.addressee_id == uid),
            )
        ).scalars().all()
        return [_serialize_friendship(f, uid) for f in rows], 200

    def post(self):
        me = _current_user()
        data = request.get_json(silent=True) or {}
        if not data.get("email"):
            return {"error": "email required"}, 400

        target = db.session.execute(
            db.select(User).where(User.email == data["email"])
        ).scalar_one_or_none()
        if target is None:
            return {"error": "User not found"}, 404
        if target.id == me.id:
            return {"error": "Cannot invite yourself"}, 400

        # reject if any friendship record already exists in either direction
        existing = db.session.execute(
            db.select(Friendship).where(
                or_(
                    (Friendship.requester_id == me.id) & (Friendship.addressee_id == target.id),
                    (Friendship.requester_id == target.id) & (Friendship.addressee_id == me.id),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return {"error": "Friendship already exists or pending"}, 409

        friendship = Friendship(requester_id=me.id, addressee_id=target.id, status=PENDING)
        db.session.add(friendship)
        db.session.commit()
        return _serialize_friendship(friendship, me.id), 201


class FriendRequestListResource(Resource):
    """GET /me/friends/requests — incoming pending invites."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        rows = db.session.execute(
            db.select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.addressee),
            )
            .where(
                Friendship.addressee_id == uid,
                Friendship.status == PENDING,
            )
        ).scalars().all()
        return [_serialize_friendship(f, uid) for f in rows], 200


class FriendResource(Resource):
    """PUT /me/friends/<id> — accept; DELETE — remove or decline."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def put(self, friendship_id):
        uid = get_jwt_identity()
        friendship = db.get_or_404(Friendship, friendship_id)

        if friendship.addressee_id != uid:
            abort(403)
        if friendship.status == ACCEPTED:
            return {"error": "Already accepted"}, 409

        friendship.status = ACCEPTED
        db.session.commit()
        return _serialize_friendship(friendship, uid), 200

    def delete(self, friendship_id):
        uid = get_jwt_identity()
        friendship = db.get_or_404(Friendship, friendship_id)

        if uid not in (friendship.requester_id, friendship.addressee_id):
            abort(403)

        db.session.delete(friendship)
        db.session.commit()
        return {}, 204


def _serialize_user(u: User) -> dict:
    sub = _active_subscription(u.id)
    is_subscribed = sub is not None and sub.status in (STATUS_ACTIVE, STATUS_CANCELLED)
    energy_boost = get_energy_boost(u)
    max_energy = ENERGY_MAX_SUBSCRIBER if is_subscribed else (ENERGY_DAILY_GUEST if u.is_guest else ENERGY_DAILY_USER)
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "currency": u.currency or DEFAULT_CURRENCY,
        "language": u.language,
        "is_guest": u.is_guest,
        "is_subscribed": is_subscribed,
        "subscription": _serialize_sub(sub) if sub else None,
        "energy": get_energy(u, is_subscribed=is_subscribed),
        "energy_boost": energy_boost,
        "max_energy": max_energy,
        "created_at": utc_isoformat(u.created_at),
        "updated_at": utc_isoformat(u.updated_at),
    }


def _serialize_friendship(f: Friendship, viewer_id: str) -> dict:
    friend = f.addressee if f.requester_id == viewer_id else f.requester
    return {
        "id": f.id,
        "friend": {"id": friend.id, "name": friend.name, "email": friend.email},
        "status": "pending" if f.status == PENDING else "accepted",
        "direction": "sent" if f.requester_id == viewer_id else "received",
        "created_at": utc_isoformat(f.created_at),
    }
