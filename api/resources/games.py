from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.models.game import Game


class GameListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        user_id = get_jwt_identity()
        games = db.session.execute(
            db.select(Game).where(Game.user_id == user_id)
        ).scalars().all()
        return [_serialize(g) for g in games], 200

    def post(self):
        data = request.get_json(silent=True) or {}
        if not data.get("challenge_id"):
            return {"error": "challenge_id required"}, 400

        game = Game(
            challenge_id=data["challenge_id"],
            user_id=get_jwt_identity(),
        )
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
