import secrets
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.common.challenge_enums import VALID_DIFFICULTIES, DIFFICULTY_LABEL
from api.models.user import User
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.user_challenge_access import UserChallengeAccess
from api.models.game import Game

CUSTOM_CHALLENGE_DAILY_LIMIT = 5
SHARE_TOKEN_LENGTH = 12
SHARE_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_SUBJECT_LENGTH = 255
MAX_SUBJECT_HINT_LENGTH = 40
AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")


def _custom_pack_id() -> str:
    row = db.session.execute(
        db.select(ChallengePack.id).where(ChallengePack.is_custom.is_(True)).limit(1)
    ).scalar_one_or_none()
    if row is None:
        abort(500, error="Custom pack is not configured")
    return row


def _today_window_in_amsterdam() -> tuple[datetime, datetime]:
    today = datetime.now(AMSTERDAM_TZ).date()
    today_start = datetime.combine(today, time.min, tzinfo=AMSTERDAM_TZ)
    return today_start, today_start + timedelta(days=1)


def _count_todays_custom_challenges(user_id: str) -> int:
    today_start, tomorrow_start = _today_window_in_amsterdam()
    return int(db.session.execute(
        db.select(func.count()).select_from(Challenge).where(
            Challenge.created_by_user_id == user_id,
            Challenge.created_at >= today_start,
            Challenge.created_at < tomorrow_start,
        )
    ).scalar_one())


def _generate_share_token() -> str:
    for _ in range(10):
        token = "".join(secrets.choice(SHARE_TOKEN_ALPHABET) for _ in range(SHARE_TOKEN_LENGTH))
        exists = db.session.execute(
            db.select(Challenge.id).where(Challenge.share_token == token)
        ).scalar_one_or_none()
        if exists is None:
            return token
    raise RuntimeError("Could not generate a unique share token")


def _serialize(
    c: Challenge,
    include_share_token: bool = False,
    *,
    user_id: str | None = None,
    games_by_challenge_id: dict[str, Game] | None = None,
) -> dict:
    game = games_by_challenge_id.get(c.id) if games_by_challenge_id else None
    payload = {
        "id": c.id,
        "subject": c.subject,
        "subject_hint": c.subject_hint,
        "difficulty": DIFFICULTY_LABEL.get(c.difficulty, c.difficulty),
        "sticker": c.sticker,
        "created_by_user_id": c.created_by_user_id,
        "created_at": utc_isoformat(c.created_at),
        "updated_at": utc_isoformat(c.updated_at),
    }
    if user_id is not None:
        payload["is_owner"] = c.created_by_user_id == user_id
    if game is not None:
        payload["game_id"] = game.id
        payload["started_at"] = utc_isoformat(game.created_at)
        payload["last_played_at"] = utc_isoformat(game.updated_at)
        payload["completed_at"] = utc_isoformat(game.completed_at)
    if include_share_token:
        payload["share_token"] = c.share_token
    return payload


def _has_access(challenge: Challenge, user_id: str) -> bool:
    if challenge.created_by_user_id == user_id:
        return True
    return db.session.execute(
        db.select(UserChallengeAccess.id).where(
            UserChallengeAccess.user_id == user_id,
            UserChallengeAccess.challenge_id == challenge.id,
        )
    ).scalar_one_or_none() is not None


class MyCustomChallengeListResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def get(self):
        uid = get_jwt_identity()
        challenges = db.session.execute(
            db.select(Challenge)
            .where(Challenge.created_by_user_id == uid)
            .order_by(Challenge.created_at.desc())
        ).scalars().all()
        return [_serialize(c, include_share_token=True) for c in challenges], 200

    def post(self):
        uid = get_jwt_identity()
        user = db.session.get(User, uid)
        if user is None:
            abort(401)
        if user.is_guest:
            return {"error": "Claim your account to create custom challenges"}, 403

        data = request.get_json(silent=True) or {}
        subject = (data.get("subject") or "").strip()
        if not subject:
            return {"error": "subject is required"}, 400
        if len(subject) > MAX_SUBJECT_LENGTH:
            return {"error": f"subject must be {MAX_SUBJECT_LENGTH} characters or fewer"}, 400

        difficulty = data.get("difficulty")
        if difficulty not in VALID_DIFFICULTIES:
            return {"error": f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}"}, 400

        subject_hint = (data.get("subject_hint") or "").strip()
        if not subject_hint:
            return {"error": "subject_hint is required"}, 400
        if len(subject_hint) > MAX_SUBJECT_HINT_LENGTH:
            return {"error": f"subject_hint must be {MAX_SUBJECT_HINT_LENGTH} characters or fewer"}, 400

        db.session.execute(
            db.select(User.id).where(User.id == uid).with_for_update()
        ).scalar_one()
        created_today = _count_todays_custom_challenges(uid)
        if created_today >= CUSTOM_CHALLENGE_DAILY_LIMIT:
            return {
                "error": "Daily custom challenge limit reached",
                "daily_limit": CUSTOM_CHALLENGE_DAILY_LIMIT,
                "created_today": created_today,
            }, 429

        challenge = Challenge(
            pack_id=_custom_pack_id(),
            subject=subject,
            subject_hint=subject_hint,
            difficulty=difficulty,
            is_active=True,
            sticker=data.get("sticker"),
            position=0,
            created_by_user_id=uid,
            share_token=_generate_share_token(),
        )
        db.session.add(challenge)
        db.session.commit()

        return _serialize(challenge, include_share_token=True), 201


class CustomChallengeListResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def get(self):
        uid = get_jwt_identity()

        access_ids = db.select(UserChallengeAccess.challenge_id).where(
            UserChallengeAccess.user_id == uid,
        )
        started_ids = db.select(Game.challenge_id).where(Game.user_id == uid)

        challenges = db.session.execute(
            db.select(Challenge)
            .where(
                Challenge.created_by_user_id.is_not(None),
                Challenge.is_active.is_(True),
                or_(
                    Challenge.created_by_user_id == uid,
                    Challenge.id.in_(access_ids),
                    Challenge.id.in_(started_ids),
                ),
            )
            .order_by(Challenge.created_at.desc())
        ).scalars().all()

        challenge_ids = [c.id for c in challenges]
        games = db.session.execute(
            db.select(Game)
            .where(Game.user_id == uid, Game.challenge_id.in_(challenge_ids))
            .order_by(Game.updated_at.desc(), Game.created_at.desc())
        ).scalars().all() if challenge_ids else []
        games_by_challenge_id = {}
        for game in games:
            games_by_challenge_id.setdefault(game.challenge_id, game)

        return [
            _serialize(
                c,
                include_share_token=c.created_by_user_id == uid,
                user_id=uid,
                games_by_challenge_id=games_by_challenge_id,
            )
            for c in challenges
        ], 200


class MyCustomChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def delete(self, challenge_id):
        return {"error": "Custom challenges cannot be deleted"}, 405


class CustomChallengeRedeemResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def post(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip()
        if not token:
            return {"error": "token is required"}, 400

        challenge = db.session.execute(
            db.select(Challenge).where(Challenge.share_token == token)
        ).scalar_one_or_none()
        if challenge is None:
            return {"error": "Invalid share token"}, 404

        if challenge.created_by_user_id != uid:
            access = UserChallengeAccess(user_id=uid, challenge_id=challenge.id)
            db.session.add(access)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

        return _serialize(challenge), 200


class CustomChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, challenge_id):
        uid = get_jwt_identity()
        challenge = db.session.get(Challenge, challenge_id)
        if challenge is None or challenge.created_by_user_id is None:
            abort(404)
        if not _has_access(challenge, uid):
            abort(403)
        return _serialize(challenge), 200
