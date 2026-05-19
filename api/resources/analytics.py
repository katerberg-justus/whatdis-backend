from datetime import datetime, timedelta, timezone
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from api import db
from api.models.user import User
from api.models.user_subscription import UserSubscription
from api.models.guess import Guess
from api.models.game import Game
from api.models.battle import Battle
from api.models.challenge import Challenge

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

        def _count(stmt):
            return db.session.execute(stmt).scalar_one()

        def _bucket(stmt, time_col):
            return {
                "all_time": _count(stmt),
                "this_week": _count(stmt.where(time_col >= week_start)),
            }

        def _split_by_guest(model, user_id_col, time_col, extra_where=()):
            def stmt_for(is_guest):
                s = (
                    db.select(func.count())
                    .select_from(model)
                    .join(User, user_id_col == User.id)
                    .where(User.is_guest == is_guest)
                )
                for clause in extra_where:
                    s = s.where(clause)
                return s
            return {
                "registered": _bucket(stmt_for(False), time_col),
                "guest": _bucket(stmt_for(True), time_col),
            }

        users_stmt = lambda is_guest: db.select(func.count()).select_from(User).where(User.is_guest == is_guest)
        subs_stmt = db.select(func.count()).select_from(UserSubscription)

        return {
            "registered_users": _bucket(users_stmt(False), User.created_at),
            "guest_users": _bucket(users_stmt(True), User.created_at),
            "subscriptions": _bucket(subs_stmt, UserSubscription.created_at),
            "guesses": _split_by_guest(Guess, Guess.user_id, Guess.created_at),
            "games": _split_by_guest(Game, Game.user_id, Game.created_at),
            # Battles bucketed by the initiator (player1).
            "battles": _split_by_guest(Battle, Battle.player1_id, Battle.created_at),
            "custom_challenges_created": _split_by_guest(
                Challenge,
                Challenge.created_by_user_id,
                Challenge.created_at,
                extra_where=(Challenge.created_by_user_id.isnot(None),),
            ),
            "custom_challenges_played": _split_by_guest(
                Game,
                Game.user_id,
                Game.created_at,
                extra_where=(
                    Game.challenge_id == Challenge.id,
                    Challenge.created_by_user_id.isnot(None),
                ),
            ),
        }, 200
