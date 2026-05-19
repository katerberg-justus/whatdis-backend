from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.models.challenge import Challenge
from api.models.challenge_rating import ChallengeRating
from api.models.game import Game


def _serialize(rating: ChallengeRating) -> dict:
    return {
        "id": rating.id,
        "challenge_id": rating.challenge_id,
        "user_id": rating.user_id,
        "rating": "like" if rating.liked else "dislike",
    }


def _completed_by_user(challenge_id: str, user_id: str) -> bool:
    return db.session.execute(
        db.select(Game.id).where(
            Game.challenge_id == challenge_id,
            Game.user_id == user_id,
            Game.completed_at.is_not(None),
        ).limit(1)
    ).scalar_one_or_none() is not None


class ChallengeRatingResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def put(self, challenge_id):
        uid = get_jwt_identity()
        challenge = db.session.get(Challenge, challenge_id)
        if challenge is None:
            abort(404)
        if not _completed_by_user(challenge_id, uid):
            return {"error": "Challenge must be completed before rating"}, 403

        data = request.get_json(silent=True) or {}
        value = data.get("rating")
        if value not in ("like", "dislike"):
            return {"error": "rating must be like or dislike"}, 400

        rating = db.session.execute(
            db.select(ChallengeRating).where(
                ChallengeRating.challenge_id == challenge_id,
                ChallengeRating.user_id == uid,
            )
        ).scalar_one_or_none()
        if rating is None:
            rating = ChallengeRating(
                challenge_id=challenge_id,
                user_id=uid,
                liked=value == "like",
            )
            db.session.add(rating)
        else:
            rating.liked = value == "like"

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Could not save rating"}, 409
        return _serialize(rating), 200
