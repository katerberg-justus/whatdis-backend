from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from api import db, limiter, cache
from api.models.daily_challenge import DailyChallenge
from api.models.challenge import Challenge
from api.models.game import Game
from api.models.user import User
from api.common.challenge_enums import VALID_DIFFICULTIES, DIFFICULTY_LABEL

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
_DAILY_SLOTS_CACHE_VERSION = "v1"


def _today_in_amsterdam() -> date:
    return datetime.now(AMSTERDAM_TZ).date()


def _seconds_until_next_amsterdam_midnight() -> int:
    now = datetime.now(AMSTERDAM_TZ)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def _daily_slots_cache_key(target: date) -> str:
    return f"daily_challenges:slots:{_DAILY_SLOTS_CACHE_VERSION}:{target.isoformat()}"


def _bust_daily_slots_cache(target: date) -> None:
    cache.delete(_daily_slots_cache_key(target))


def _current_user_optional() -> User | None:
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            return db.session.get(User, uid)
    except Exception:
        pass
    return None


def _completed_challenge_ids(user: User) -> set:
    """Return the set of challenge_ids the user has won."""
    rows = db.session.execute(
        db.select(Game.challenge_id)
        .where(Game.user_id == user.id, Game.completed_at.is_not(None))
    ).scalars().all()
    return set(rows)


def _serialize(dc: DailyChallenge, completed: bool = False) -> dict:
    return {
        "id": dc.id,
        "challenge_id": dc.challenge_id,
        "available_on": dc.available_on.isoformat(),
        "difficulty": DIFFICULTY_LABEL.get(dc.difficulty, dc.difficulty),
        "completed": completed,
        "subject": dc.challenge.subject if (completed and dc.challenge) else None,
        "subject_hint": dc.challenge.subject_hint if (completed and dc.challenge) else None,
        "sticker": dc.challenge.sticker if (completed and dc.challenge) else None,
    }


def _slot_payload(dc: DailyChallenge) -> dict:
    challenge = dc.challenge
    return {
        "id": dc.id,
        "challenge_id": dc.challenge_id,
        "available_on": dc.available_on.isoformat(),
        "difficulty": dc.difficulty,
        "subject": challenge.subject if challenge else None,
        "subject_hint": challenge.subject_hint if challenge else None,
        "sticker": challenge.sticker if challenge else None,
    }


def _serialize_slot_payload(slot: dict, completed: bool = False) -> dict:
    return {
        "id": slot["id"],
        "challenge_id": slot["challenge_id"],
        "available_on": slot["available_on"],
        "difficulty": DIFFICULTY_LABEL.get(slot["difficulty"], slot["difficulty"]),
        "completed": completed,
        "subject": slot["subject"] if completed else None,
        "subject_hint": slot["subject_hint"] if completed else None,
        "sticker": slot["sticker"] if completed else None,
    }


def _daily_slots_for_date(target: date) -> list[DailyChallenge]:
    rows = db.session.execute(
        db.select(DailyChallenge)
        .join(Challenge, DailyChallenge.challenge_id == Challenge.id)
        .where(DailyChallenge.available_on == target)
        .order_by(
            DailyChallenge.difficulty,
            DailyChallenge.updated_at.desc(),
            DailyChallenge.created_at.desc(),
        )
    ).scalars().all()

    slots = []
    seen_difficulties = set()
    for slot in rows:
        if slot.difficulty in seen_difficulties:
            continue
        seen_difficulties.add(slot.difficulty)
        slots.append(slot)
    return slots


def _cached_daily_slot_payloads_for_date(target: date) -> list[dict]:
    key = _daily_slots_cache_key(target)
    hit = cache.get(key)
    if hit is not None:
        return hit

    slots = [_slot_payload(slot) for slot in _daily_slots_for_date(target)]
    cache.set(key, slots, timeout=_seconds_until_next_amsterdam_midnight())
    return slots


class DailyChallengeListResource(Resource):
    decorators = [limiter.limit("60 per minute")]

    def get(self):
        user = _current_user_optional()

        today_slots = _cached_daily_slot_payloads_for_date(_today_in_amsterdam())

        completed_ids = _completed_challenge_ids(user) if user else set()

        return [
            _serialize_slot_payload(slot, slot["challenge_id"] in completed_ids)
            for slot in today_slots
        ], 200

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
            difficulty=challenge.difficulty,
        )
        db.session.add(slot)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return {"error": "A daily slot for that difficulty on that date already exists"}, 409

        _bust_daily_slots_cache(available_on)
        return _serialize(slot), 201


class DailyChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def get(self, daily_id):
        dc = db.get_or_404(DailyChallenge, daily_id)
        user = db.session.get(User, get_jwt_identity())
        completed = dc.challenge_id in _completed_challenge_ids(user)
        return _serialize(dc, completed), 200

    def delete(self, daily_id):
        dc = db.get_or_404(DailyChallenge, daily_id)
        available_on = dc.available_on
        db.session.delete(dc)
        db.session.commit()
        _bust_daily_slots_cache(available_on)
        return {}, 204


class DailyChallengeByDateResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, date_str):
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            return {"error": "Date must be YYYY-MM-DD"}, 400

        today = _today_in_amsterdam()
        user = db.session.get(User, get_jwt_identity())
        if target != today and not user.is_subscribed:
            return {"error": "Subscription required to view non-today schedules"}, 403

        slots = (
            _cached_daily_slot_payloads_for_date(target)
            if target == today
            else _daily_slots_for_date(target)
        )
        completed_ids = _completed_challenge_ids(user)
        if target == today:
            return [
                _serialize_slot_payload(slot, slot["challenge_id"] in completed_ids)
                for slot in slots
            ], 200
        return [_serialize(dc, dc.challenge_id in completed_ids) for dc in slots], 200
