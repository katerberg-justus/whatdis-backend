from datetime import date
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.common.challenge_enums import DIFFICULTY_LABEL
from api.common.limits import guess_limit_for
from api.models.game import Game
from api.models.guess import Guess
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.daily_challenge import DailyChallenge
from api.models.user import User


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

        pack = db.session.get(ChallengePack, challenge.pack_id)
        if pack is None:
            return {"error": "Challenge not found"}, 404
        if pack.is_battle:
            return {"error": "Battle challenges cannot be started as ordinary games"}, 400

        if not is_daily:
            from api.resources.challenge_packs import _has_access
            if not challenge.is_active or challenge.sticker is None:
                return {"error": "Challenge not found"}, 404
            if not _has_access(pack, uid):
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
    pack = db.session.get(ChallengePack, challenge.pack_id) if challenge else None
    next_challenge = _next_challenge(challenge)
    user = db.session.get(User, g.user_id)
    is_daily = _is_daily_game(g, challenge)

    return {
        "id": g.id,
        "challenge_id": g.challenge_id,
        "user_id": g.user_id,
        "completed_at": utc_isoformat(g.completed_at),
        "guess_count": guess_count,
        "duration_seconds": duration_seconds,
        "challenge": _serialize_challenge(
            challenge,
            completed=g.completed_at is not None,
            is_daily=is_daily,
        ),
        "pack_id": challenge.pack_id if challenge else None,
        "pack_name": pack.name if pack else None,
        "position": _ordinal_position(challenge),
        "difficulty": DIFFICULTY_LABEL.get(challenge.difficulty) if challenge else None,
        "guess_limit": guess_limit_for(user),
        "next_challenge": _serialize_next(next_challenge),
        "created_at": utc_isoformat(g.created_at),
        "updated_at": utc_isoformat(g.updated_at),
    }


def _serialize_challenge(
    challenge: Challenge | None,
    completed: bool = False,
    is_daily: bool = False,
) -> dict | None:
    if challenge is None:
        return None

    return {
        "id": challenge.id,
        "is_daily": is_daily,
        "subject": challenge.subject if completed else None,
        "sticker": challenge.sticker if completed else None,
    }


def _is_daily_game(game: Game, challenge: Challenge | None) -> bool:
    if challenge is None or game.created_at is None:
        return False
    return db.session.execute(
        db.select(DailyChallenge.id).where(
            DailyChallenge.challenge_id == challenge.id,
            DailyChallenge.available_on == game.created_at.date(),
        )
    ).scalar_one_or_none() is not None


def _next_challenge(challenge: Challenge | None) -> Challenge | None:
    if challenge is None:
        return None
    from api.resources.challenge_packs import _public_challenge_filters
    return db.session.execute(
        db.select(Challenge)
        .where(
            Challenge.pack_id == challenge.pack_id,
            *_public_challenge_filters(),
            Challenge.position > challenge.position,
        )
        .order_by(Challenge.position.asc())
        .limit(1)
    ).scalar_one_or_none()


def _serialize_next(challenge: Challenge | None) -> dict | None:
    if challenge is None:
        return None
    return {
        "id": challenge.id,
        "position": _ordinal_position(challenge),
        "difficulty": DIFFICULTY_LABEL.get(challenge.difficulty),
    }


def _ordinal_position(challenge: Challenge | None) -> int | None:
    """1-based rank of an active challenge within its pack, ordered by position."""
    if challenge is None:
        return None
    rank = db.session.execute(
        db.select(func.count(Challenge.id)).where(
            Challenge.pack_id == challenge.pack_id,
            Challenge.is_active.is_(True),
            Challenge.position <= challenge.position,
        )
    ).scalar_one()
    return int(rank)
