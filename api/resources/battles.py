from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, func
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.battle import Battle, PENDING, ACTIVE, FINISHED
from api.models.battle_guess import BattleGuess
from api.models.user import User
from api.common.response_codes import VALID_CODES, WIN
from api.common.energy import consume_energy


def _get_battle_or_404(battle_id: str) -> Battle:
    return db.get_or_404(Battle, battle_id)


def _require_participant(battle: Battle, uid: str):
    if uid not in (battle.player1_id, battle.player2_id):
        abort(403)


def _other_player(battle: Battle, uid: str) -> str:
    return battle.player2_id if battle.player1_id == uid else battle.player1_id


class BattleListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        battles = db.session.execute(
            db.select(Battle).where(
                or_(Battle.player1_id == uid, Battle.player2_id == uid)
            )
        ).scalars().all()
        return [_serialize(b, uid) for b in battles], 200

    def post(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("challenge_id", "opponent_id") if not data.get(f)]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400
        if data["opponent_id"] == uid:
            return {"error": "Cannot battle yourself"}, 400

        opponent = db.session.get(User, data["opponent_id"])
        if opponent is None:
            return {"error": "Opponent not found"}, 404

        battle = Battle(
            challenge_id=data["challenge_id"],
            player1_id=uid,
            player2_id=data["opponent_id"],
            status=PENDING,
        )
        db.session.add(battle)
        db.session.commit()
        return _serialize(battle, uid), 201


class BattleResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, battle_id):
        uid = get_jwt_identity()
        battle = _get_battle_or_404(battle_id)
        _require_participant(battle, uid)
        return _serialize(battle, uid, include_guesses=True), 200

    def delete(self, battle_id):
        """Player1 cancels a pending battle, or player2 declines."""
        uid = get_jwt_identity()
        battle = _get_battle_or_404(battle_id)
        _require_participant(battle, uid)

        if battle.status != PENDING:
            return {"error": "Only pending battles can be cancelled"}, 409

        db.session.delete(battle)
        db.session.commit()
        return {}, 204


class BattleAcceptResource(Resource):
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def put(self, battle_id):
        """Player2 accepts — battle becomes active, player1 goes first."""
        uid = get_jwt_identity()
        battle = _get_battle_or_404(battle_id)

        if battle.player2_id != uid:
            abort(403)
        if battle.status != PENDING:
            return {"error": "Battle is not pending"}, 409

        battle.status = ACTIVE
        battle.current_turn_id = battle.player1_id
        db.session.commit()
        return _serialize(battle, uid), 200


class BattleGuessListResource(Resource):
    decorators = [jwt_required(), limiter.limit("60 per minute")]

    def get(self, battle_id):
        uid = get_jwt_identity()
        battle = _get_battle_or_404(battle_id)
        _require_participant(battle, uid)
        guesses = battle.guesses.all()
        return [_serialize_guess(g) for g in guesses], 200

    def post(self, battle_id):
        uid = get_jwt_identity()
        battle = _get_battle_or_404(battle_id)
        _require_participant(battle, uid)

        if battle.status == PENDING:
            return {"error": "Battle has not started yet"}, 409
        if battle.status == FINISHED:
            return {"error": "Battle is already finished"}, 409
        if battle.current_turn_id != uid:
            return {"error": "Not your turn"}, 403

        data = request.get_json(silent=True) or {}
        if not data.get("content"):
            return {"error": "content required"}, 400
        if data.get("response_code") is None:
            return {"error": "response_code required"}, 400

        rc = data["response_code"]
        if not isinstance(rc, int) or rc not in VALID_CODES:
            return {"error": f"response_code must be one of {sorted(VALID_CODES)}"}, 400

        user = db.session.get(User, uid)
        allowed, energy_remaining = consume_energy(user, request.remote_addr)
        if not allowed:
            return {"error": "No energy remaining. Come back tomorrow."}, 429

        next_turn = db.session.execute(
            db.select(func.count()).select_from(BattleGuess).where(BattleGuess.battle_id == battle_id)
        ).scalar_one()

        guess = BattleGuess(
            battle_id=battle_id,
            user_id=uid,
            content=data["content"],
            response_code=rc,
            turn_number=next_turn + 1,
        )
        db.session.add(guess)

        if rc == WIN:
            battle.status = FINISHED
            battle.winner_id = uid
            battle.current_turn_id = None
        else:
            battle.current_turn_id = _other_player(battle, uid)

        db.session.commit()
        return {**_serialize_guess(guess), "energy_remaining": energy_remaining}, 201


def _serialize(battle: Battle, viewer_id: str, include_guesses: bool = False) -> dict:
    status_label = {PENDING: "pending", ACTIVE: "active", FINISHED: "finished"}
    data = {
        "id": battle.id,
        "challenge_id": battle.challenge_id,
        "player1": {"id": battle.player1.id, "name": battle.player1.name},
        "player2": {"id": battle.player2.id, "name": battle.player2.name},
        "status": status_label[battle.status],
        "current_turn_id": battle.current_turn_id,
        "winner_id": battle.winner_id,
        "created_at": utc_isoformat(battle.created_at),
        "updated_at": utc_isoformat(battle.updated_at),
    }
    if include_guesses:
        data["guesses"] = [_serialize_guess(g) for g in battle.guesses.all()]
    return data


def _serialize_guess(g: BattleGuess) -> dict:
    rc_labels = {0: "no", 1: "yes", 2: "indecisive", 3: "refusal", 4: "win", 5: "possible", 6: "possibly_not"}
    return {
        "id": g.id,
        "battle_id": g.battle_id,
        "user_id": g.user_id,
        "content": g.content,
        "response_code": g.response_code,
        "response": rc_labels.get(g.response_code, str(g.response_code)),
        "turn_number": g.turn_number,
        "created_at": utc_isoformat(g.created_at),
    }
