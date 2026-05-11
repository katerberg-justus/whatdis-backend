from datetime import datetime, timezone
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.models.game import Game
from api.models.guess import Guess
from api.models.challenge import Challenge
from api.models.user import User
from api.common.energy import consume_energy
from api.common.response_codes import WIN
from api.services.ai import judge_guess


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
        uid = get_jwt_identity()
        game = db.get_or_404(Game, game_id)
        _require_owner(game)

        data = request.get_json(silent=True) or {}
        content = data.get("content", "").strip()
        if not content:
            return {"error": "Missing field: content"}, 400

        challenge = db.session.get(Challenge, game.challenge_id)
        if challenge is None:
            return {"error": "Challenge not found"}, 404

        user = db.session.get(User, uid)
        allowed, energy_remaining = consume_energy(user, request.remote_addr)
        if not allowed:
            return {"error": "No energy remaining. Come back tomorrow."}, 429

        prior_guesses = db.session.execute(
            db.select(Guess).where(Guess.game_id == game_id).order_by(Guess.created_at)
        ).scalars().all()
        prior = [{"content": g.content, "response_code": g.response_code} for g in prior_guesses]

        rc = judge_guess(challenge.subject, challenge.challenge_type, content, prior)

        if rc == WIN and game.completed_at is None:
            game.completed_at = datetime.now(timezone.utc)

        guess = Guess(
            game_id=game_id,
            user_id=uid,
            content=content,
            response_code=rc,
        )
        db.session.add(guess)
        db.session.commit()
        return {**_serialize(guess), "energy_remaining": energy_remaining}, 201


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
    rc_labels = {0: "no", 1: "yes", 2: "indecisive", 3: "refusal", 4: "win", 5: "possible"}
    return {
        "id": g.id,
        "game_id": g.game_id,
        "user_id": g.user_id,
        "content": g.content,
        "response_code": g.response_code,
        "response": rc_labels.get(g.response_code, str(g.response_code)),
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
