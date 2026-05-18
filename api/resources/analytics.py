from datetime import datetime, timedelta, timezone
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from api import db
from api.models.user import User
from api.models.user_subscription import UserSubscription

ADMIN_EMAIL = "justuskaterberg@hotmail.com"


def _start_of_week_utc() -> datetime:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (start_of_day - timedelta(days=start_of_day.weekday())).replace(tzinfo=None)


class AnalyticsResource(Resource):
    decorators = [jwt_required()]

    def get(self):
        user = db.session.get(User, get_jwt_identity())
        if user is None or user.email != ADMIN_EMAIL:
            abort(403, message="Forbidden")

        week_start = _start_of_week_utc()

        def _count(model, *where):
            stmt = db.select(func.count()).select_from(model)
            for clause in where:
                stmt = stmt.where(clause)
            return db.session.execute(stmt).scalar_one()

        return {
            "registered_users": {
                "all_time": _count(User, User.is_guest == False),
                "this_week": _count(User, User.is_guest == False, User.created_at >= week_start),
            },
            "guest_users": {
                "all_time": _count(User, User.is_guest == True),
                "this_week": _count(User, User.is_guest == True, User.created_at >= week_start),
            },
            "subscriptions": {
                "all_time": _count(UserSubscription),
                "this_week": _count(UserSubscription, UserSubscription.created_at >= week_start),
            },
        }, 200
