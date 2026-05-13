import re
from datetime import datetime, timezone
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.game import Game
from api.models.guess import Guess
from api.models.challenge import Challenge
from api.models.user import User
from api.common.energy import consume_energy
from api.common.response_codes import WIN
from api.common.achievements import check_after_guess
from api.resources.subscriptions import _active_subscription
from api.common.subscription_plans import STATUS_ACTIVE, STATUS_CANCELLED
from api.services.ai import judge_guess

MIN_GUESS_LENGTH = 2
MAX_GUESS_LENGTH = 80


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
        content = _clean_guess_content(data.get("content", ""))
        if not content:
            return {"error": "Missing field: content"}, 400
        if not MIN_GUESS_LENGTH <= len(content) <= MAX_GUESS_LENGTH:
            return {"error": f"Guess must be between {MIN_GUESS_LENGTH} and {MAX_GUESS_LENGTH} characters"}, 400

        challenge = db.session.get(Challenge, game.challenge_id)
        if challenge is None:
            return {"error": "Challenge not found"}, 404

        user = db.session.get(User, uid)
        sub = _active_subscription(uid)
        is_subscribed = sub is not None and sub.status in (STATUS_ACTIVE, STATUS_CANCELLED)
        allowed, energy_remaining = consume_energy(user, request.remote_addr, is_subscribed=is_subscribed)
        if not allowed:
            return {"error": "No energy remaining. Come back tomorrow."}, 429

        prior_guesses = db.session.execute(
            db.select(Guess).where(Guess.game_id == game_id).order_by(Guess.created_at)
        ).scalars().all()
        prior = [{"content": g.content, "response_code": g.response_code} for g in prior_guesses]

        rc = judge_guess(challenge.subject, content, prior)

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

        if user:
            check_after_guess(user, won=(rc == WIN))
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


def _clean_guess_content(content: str) -> str:
    content = re.sub(r"\s+", " ", str(content)).strip()
    content = re.sub(r"([?!.,]){2,}", r"\1", content)
    return content


def _serialize(g: Guess) -> dict:
    rc_labels = {0: "no", 1: "yes", 2: "indecisive", 3: "refusal", 4: "win", 5: "possible", 6: "possibly_not"}
    return {
        "id": g.id,
        "game_id": g.game_id,
        "user_id": g.user_id,
        "content": g.content,
        "response_code": g.response_code,
        "response": rc_labels.get(g.response_code, str(g.response_code)),
        "created_at": utc_isoformat(g.created_at),
        "updated_at": utc_isoformat(g.updated_at),
    }
