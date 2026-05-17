from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import select, case
from api import db, limiter, cache
from api.common.base_model import utc_isoformat
from api.models.achievement import Achievement
from api.models.user_achievement import UserAchievement

_ACHIEVEMENT_DEFINITIONS_CACHE_KEY = "achievements:definitions:v1"
_ACHIEVEMENT_DEFINITIONS_TTL = 3600

_CATEGORY_ORDER = case(
    (Achievement.category == "guesses", 1),
    (Achievement.category == "wins",    2),
    (Achievement.category == "daily",   3),
    (Achievement.category == "streak",  4),
    else_=5,
)


class AchievementListResource(Resource):
    """GET /achievements — all achievements; JWT optional.
    name/description are revealed only for earned achievements and the next
    unearned one in each category. Everything else is redacted.
    """

    def get(self):
        try:
            verify_jwt_in_request(optional=True)
            uid = get_jwt_identity()
        except Exception:
            uid = None

        achievements = _achievement_definitions()

        earned_ids = set()
        if uid:
            earned_ids = {
                row[0] for row in db.session.execute(
                    select(UserAchievement.achievement_id).where(UserAchievement.user_id == uid)
                ).all()
            }

        next_ids = _next_per_category(achievements, earned_ids)

        return [
            _serialize(a, earned=a["id"] in earned_ids, revealed=a["id"] in earned_ids or a["id"] in next_ids)
            for a in achievements
        ], 200


class MeAchievementListResource(Resource):
    """GET /me/achievements — only the achievements the current user has earned."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        earned_at_by_id = {
            row.achievement_id: row.earned_at
            for row in db.session.execute(
                select(UserAchievement).where(UserAchievement.user_id == uid)
            ).scalars().all()
        }
        return [
            _serialize_earned(a, earned_at_by_id[a["id"]])
            for a in _achievement_definitions()
            if a["id"] in earned_at_by_id
        ], 200


def _achievement_definitions() -> list[dict]:
    hit = cache.get(_ACHIEVEMENT_DEFINITIONS_CACHE_KEY)
    if hit is not None:
        return hit

    achievements = db.session.execute(
        select(Achievement).order_by(_CATEGORY_ORDER, Achievement.threshold)
    ).scalars().all()
    payload = [
        {
            "id": a.id,
            "category": a.category,
            "threshold": a.threshold,
            "name": a.name,
            "description": a.description,
            "icon": a.icon,
        }
        for a in achievements
    ]
    cache.set(_ACHIEVEMENT_DEFINITIONS_CACHE_KEY, payload, timeout=_ACHIEVEMENT_DEFINITIONS_TTL)
    return payload


def _next_per_category(achievements: list, earned_ids: set) -> set:
    """Return the ID of the lowest-threshold unearned achievement per category."""
    next_ids: set = set()
    seen: set = set()
    for a in achievements:  # already ordered by category then threshold
        if a["category"] not in seen and a["id"] not in earned_ids:
            next_ids.add(a["id"])
            seen.add(a["category"])
    return next_ids


def _serialize(a: dict, earned: bool = False, revealed: bool = True) -> dict:
    return {
        "id": a["id"],
        "category": a["category"],
        "threshold": a["threshold"],
        "name": a["name"] if revealed else None,
        "description": a["description"] if revealed else None,
        "icon": a["icon"] if earned else None,
        "earned": earned,
    }


def _serialize_earned(a: dict, earned_at) -> dict:
    return {
        **_serialize(a, earned=True, revealed=True),
        "earned_at": utc_isoformat(earned_at),
    }
