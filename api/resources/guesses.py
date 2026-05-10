from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.models.game import Game
from api.models.guess import Guess


class GuessListResource(Resource):
    decorators = [jwt_required(), limiter.limit("60 per minute")]

    def get(self, game_id):
        game = db.get_or_404(Game, game_id)
        _require_owner(game)
        guesses = db.session.execute(
            db.select(Guess).where(Guess.game_id == game_id)
        ).scalars().all()
        return [_serialize(g) for g in guesses], 200

    def post(self, game_id):
        game = db.get_or_404(Game, game_id)
        _require_owner(game)

        data = request.get_json(silent=True) or {}
        missing = [f for f in ("content", "response_code") if data.get(f) is None]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400

        rc = data["response_code"]
        if not isinstance(rc, int) or not (0 <= rc <= 255):
            return {"error": "response_code must be an integer 0–255"}, 400

        guess = Guess(
            game_id=game_id,
            user_id=get_jwt_identity(),
            content=data["content"],
            response_code=rc,
        )
        db.session.add(guess)
        db.session.commit()
        return _serialize(guess), 201


class GuessResource(Resource):
    decorators = [jwt_required(), limiter.limit("60 per minute")]

    def get(self, game_id, guess_id):
        guess = _get_guess(game_id, guess_id)
        return _serialize(guess), 200

    def delete(self, game_id, guess_id):
        guess = _get_guess(game_id, guess_id)
        db.session.delete(guess)
        db.session.commit()
        return {}, 204


def _get_guess(game_id: str, guess_id: str) -> Guess:
    game = db.get_or_404(Game, game_id)
    _require_owner(game)
    guess = db.session.execute(
        db.select(Guess).where(Guess.id == guess_id, Guess.game_id == game_id)
    ).scalar_one_or_none()
    if guess is None:
        from flask_restful import abort
        abort(404)
    return guess


def _require_owner(game: Game):
    if get_jwt_identity() != game.user_id:
        from flask_restful import abort
        abort(403)


def _serialize(g: Guess) -> dict:
    return {
        "id": g.id,
        "game_id": g.game_id,
        "user_id": g.user_id,
        "content": g.content,
        "response_code": g.response_code,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
