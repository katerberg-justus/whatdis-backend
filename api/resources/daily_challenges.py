from datetime import date
from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from api import db, limiter
from api.models.daily_challenge import DailyChallenge
from api.models.challenge import Challenge
from api.models.user import User
from api.common.challenge_enums import (
    VALID_CHALLENGE_TYPES, VALID_DIFFICULTIES,
    CHALLENGE_TYPE_LABEL, DIFFICULTY_LABEL,
)
from api.common.limits import daily_limit_for, guess_limit_for


def _current_user_optional() -> User | None:
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            return db.session.get(User, uid)
    except Exception:
        pass
    return None


def _todays_games_count(user: User) -> int:
    """Count distinct daily challenge games this user started today."""
    from api.models.game import Game
    from sqlalchemy import func, cast, Date
    return db.session.execute(
        db.select(func.count()).select_from(Game).join(
            DailyChallenge, DailyChallenge.challenge_id == Game.challenge_id
        ).where(
            Game.user_id == user.id,
            DailyChallenge.available_on == date.today(),
        )
    ).scalar_one()


def _serialize(dc: DailyChallenge, guess_limit: int) -> dict:
    return {
        "id": dc.id,
        "challenge_id": dc.challenge_id,
        "available_on": dc.available_on.isoformat(),
        "challenge_type": CHALLENGE_TYPE_LABEL.get(dc.challenge_type, dc.challenge_type),
        "difficulty": DIFFICULTY_LABEL.get(dc.difficulty, dc.difficulty),
        "guess_limit": guess_limit,
        "subject": dc.challenge.subject if dc.challenge else None,
    }


class DailyChallengeListResource(Resource):
    decorators = [limiter.limit("60 per minute")]

    def get(self):
        user = _current_user_optional()
        limit = daily_limit_for(user)
        guess_limit = guess_limit_for(user)

        today_slots = db.session.execute(
            db.select(DailyChallenge)
            .where(DailyChallenge.available_on == date.today())
            .order_by(DailyChallenge.challenge_type, DailyChallenge.difficulty)
        ).scalars().all()

        if user and user.is_subscribed:
            # subscribers see all slots
            return [_serialize(dc, guess_limit) for dc in today_slots], 200

        # non-subscribers see all slots but know they can only play `limit` of them
        return {
            "daily_limit": limit,
            "challenges": [_serialize(dc, guess_limit) for dc in today_slots],
        }, 200

    @jwt_required()
    def post(self):
        """Schedule a challenge as a daily slot."""
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("challenge_id", "available_on") if not data.get(f)]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400

        try:
            available_on = date.fromisoformat(data["available_on"])
        except ValueError:
            return {"error": "available_on must be a date string (YYYY-MM-DD)"}, 400

        challenge = db.session.get(Challenge, data["challenge_id"])
        if challenge is None:
            return {"error": "Challenge not found"}, 404

        slot = DailyChallenge(
            challenge_id=challenge.id,
            available_on=available_on,
            challenge_type=challenge.challenge_type,
            difficulty=challenge.difficulty,
        )
        db.session.add(slot)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {"error": "A daily slot for that type/difficulty on that date already exists"}, 409

        return _serialize(slot, guess_limit_for(None)), 201


class DailyChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def get(self, daily_id):
        dc = db.get_or_404(DailyChallenge, daily_id)
        user = db.session.get(User, get_jwt_identity())
        return _serialize(dc, guess_limit_for(user)), 200

    def delete(self, daily_id):
        dc = db.get_or_404(DailyChallenge, daily_id)
        db.session.delete(dc)
        db.session.commit()
        return {}, 204


class DailyChallengeByDateResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, date_str):
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            return {"error": "Date must be YYYY-MM-DD"}, 400

        user = db.session.get(User, get_jwt_identity())
        if target != date.today() and not user.is_subscribed:
            return {"error": "Subscription required to view non-today schedules"}, 403

        slots = db.session.execute(
            db.select(DailyChallenge)
            .where(DailyChallenge.available_on == target)
            .order_by(DailyChallenge.challenge_type, DailyChallenge.difficulty)
        ).scalars().all()
        return [_serialize(dc, guess_limit_for(user)) for dc in slots], 200
