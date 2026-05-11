from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from sqlalchemy import select, case
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.achievement import Achievement
from api.models.user_achievement import UserAchievement

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

        achievements = db.session.execute(
            select(Achievement).order_by(_CATEGORY_ORDER, Achievement.threshold)
        ).scalars().all()

        earned_ids = set()
        if uid:
            earned_ids = {
                row[0] for row in db.session.execute(
                    select(UserAchievement.achievement_id).where(UserAchievement.user_id == uid)
                ).all()
            }

        next_ids = _next_per_category(achievements, earned_ids)

        return [
            _serialize(a, earned=a.id in earned_ids, revealed=a.id in earned_ids or a.id in next_ids)
            for a in achievements
        ], 200


class MeAchievementListResource(Resource):
    """GET /me/achievements — only the achievements the current user has earned."""
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        rows = db.session.execute(
            select(UserAchievement)
            .where(UserAchievement.user_id == uid)
            .join(UserAchievement.achievement)
            .order_by(_CATEGORY_ORDER, Achievement.threshold)
        ).scalars().all()
        return [_serialize_earned(ua) for ua in rows], 200


def _next_per_category(achievements: list, earned_ids: set) -> set:
    """Return the ID of the lowest-threshold unearned achievement per category."""
    next_ids: set = set()
    seen: set = set()
    for a in achievements:  # already ordered by category then threshold
        if a.category not in seen and a.id not in earned_ids:
            next_ids.add(a.id)
            seen.add(a.category)
    return next_ids


def _serialize(a: Achievement, earned: bool = False, revealed: bool = True) -> dict:
    return {
        "id": a.id,
        "category": a.category,
        "threshold": a.threshold,
        "name": a.name if revealed else None,
        "description": a.description if revealed else None,
        "icon": a.icon if earned else None,
        "earned": earned,
    }


def _serialize_earned(ua: UserAchievement) -> dict:
    return {
        **_serialize(ua.achievement, earned=True, revealed=True),
        "earned_at": utc_isoformat(ua.earned_at),
    }
