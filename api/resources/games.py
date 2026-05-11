from datetime import date
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.models.game import Game
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
    return {
        "id": g.id,
        "challenge_id": g.challenge_id,
        "user_id": g.user_id,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
