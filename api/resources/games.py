from datetime import date
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.game import Game
from api.models.guess import Guess
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.daily_challenge import DailyChallenge


class GameListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        user_id = get_jwt_identity()
        games = db.session.execute(
            db.select(Game).where(Game.user_id == user_id)
        ).scalars().all()
        return [_serialize(g) for g in games], 200

    def post(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        if not data.get("challenge_id"):
            return {"error": "challenge_id required"}, 400

        challenge_id = data["challenge_id"]

        challenge = db.session.get(Challenge, challenge_id)
        if challenge is None:
            return {"error": "Challenge not found"}, 404

        is_daily = db.session.execute(
            db.select(DailyChallenge).where(
                DailyChallenge.challenge_id == challenge_id,
                DailyChallenge.available_on == date.today(),
            )
        ).scalar_one_or_none() is not None

        if not is_daily:
            from api.resources.challenge_packs import _has_access
            pack = db.session.get(ChallengePack, challenge.pack_id)
            if pack is None or not _has_access(pack, uid):
                return {"error": "Pack access required"}, 403

        existing = db.session.execute(
            db.select(Game).where(
                Game.user_id == uid,
                Game.challenge_id == challenge_id,
            )
        ).scalar_one_or_none()
        if existing:
            return _serialize(existing), 200

        game = Game(challenge_id=challenge_id, user_id=uid)
        db.session.add(game)
        db.session.commit()
        return _serialize(game), 201


class GameResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, game_id):
        game = db.get_or_404(Game, game_id)
        _require_owner(game)
        return _serialize(game), 200

    def delete(self, game_id):
        game = db.get_or_404(Game, game_id)
        _require_owner(game)
        db.session.delete(game)
        db.session.commit()
        return {}, 204


def _require_owner(game: Game):
    if get_jwt_identity() != game.user_id:
        from flask_restful import abort
        abort(403)


def _serialize(g: Game) -> dict:
    guess_count = db.session.execute(
        db.select(func.count(Guess.id)).where(Guess.game_id == g.id)
    ).scalar_one()

    duration_seconds = None
    if g.completed_at is not None:
        first_guess_at = db.session.execute(
            db.select(func.min(Guess.created_at)).where(Guess.game_id == g.id)
        ).scalar_one()
        if first_guess_at is not None:
            duration_seconds = int((g.completed_at - first_guess_at).total_seconds())

    challenge = db.session.get(Challenge, g.challenge_id)

    return {
        "id": g.id,
        "challenge_id": g.challenge_id,
        "user_id": g.user_id,
        "completed_at": utc_isoformat(g.completed_at),
        "guess_count": guess_count,
        "duration_seconds": duration_seconds,
        "challenge": _serialize_challenge(challenge),
        "created_at": utc_isoformat(g.created_at),
        "updated_at": utc_isoformat(g.updated_at),
    }


def _serialize_challenge(challenge: Challenge | None) -> dict | None:
    if challenge is None:
        return None

    return {
        "id": challenge.id,
        "subject": challenge.subject,
        "icon": challenge.icon,
    }
