from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, func
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.battle import Battle, PENDING, ACTIVE, FINISHED
from api.models.battle_guess import BattleGuess
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.friendship import Friendship, ACCEPTED
from api.models.user import User
from api.common.challenge_enums import DIFFICULTY_LABEL
from api.common.response_codes import WIN
from api.common.energy import consume_energy
from api.common.achievements import check_after_battle_guess
from api.services.ai import judge_guess


def _get_battle_or_404(battle_id: str) -> Battle:
    return db.get_or_404(Battle, battle_id)


def _require_participant(battle: Battle, uid: str):
    if uid not in (battle.player1_id, battle.player2_id):
        abort(403)


def _other_player(battle: Battle, uid: str) -> str:
    return battle.player2_id if battle.player1_id == uid else battle.player1_id


def _are_accepted_friends(user_id: str, other_user_id: str) -> bool:
    return db.session.execute(
        db.select(Friendship.id).where(
            Friendship.status == ACCEPTED,
            or_(
                (Friendship.requester_id == user_id) & (Friendship.addressee_id == other_user_id),
                (Friendship.requester_id == other_user_id) & (Friendship.addressee_id == user_id),
            ),
        )
    ).scalar_one_or_none() is not None


def _require_battle_challenge(challenge_id: str, uid: str) -> Challenge:
    challenge = db.session.get(Challenge, challenge_id)
    if challenge is None or not challenge.is_active or challenge.sticker is None:
        abort(404, error="Challenge not found")

    pack = db.session.get(ChallengePack, challenge.pack_id)
    if pack is None:
        abort(404, error="Challenge not found")
    if not pack.is_battle:
        abort(400, error="Only battle challenges can be used for battles")

    from api.resources.challenge_packs import _has_access
    if not _has_access(pack, uid):
        abort(403, error="Pack access required")
    return challenge


def _completed_battle_challenge_ids(pack_id: str, user_ids: list[str]) -> set:
    if not user_ids:
        return set()

    rows = db.session.execute(
        db.select(Battle.challenge_id)
        .join(Challenge, Challenge.id == Battle.challenge_id)
        .where(
            Challenge.pack_id == pack_id,
            Challenge.is_active == True,
            Challenge.sticker.is_not(None),
            Battle.status == FINISHED,
            or_(Battle.player1_id.in_(user_ids), Battle.player2_id.in_(user_ids)),
        )
    ).scalars().all()
    return set(rows)


def _serialize_battle_picker_challenge(challenge: Challenge, completed_by_participant: bool) -> dict:
    return {
        "id": challenge.id,
        "pack_id": challenge.pack_id,
        "position": challenge.position,
        "difficulty": DIFFICULTY_LABEL.get(challenge.difficulty, challenge.difficulty),
        "is_active": challenge.is_active,
        "is_locked": False,
        "battle_completed_by_participant": completed_by_participant,
        "created_at": utc_isoformat(challenge.created_at),
        "updated_at": utc_isoformat(challenge.updated_at),
    }


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

        _require_battle_challenge(data["challenge_id"], uid)

        opponent = db.session.get(User, data["opponent_id"])
        if opponent is None:
            return {"error": "Opponent not found"}, 404

        pair_filter = or_(
            (Battle.player1_id == uid) & (Battle.player2_id == data["opponent_id"]),
            (Battle.player1_id == data["opponent_id"]) & (Battle.player2_id == uid),
        )

        pending_exists = db.session.execute(
            db.select(func.count()).select_from(Battle).where(
                pair_filter,
                Battle.status == PENDING,
            )
        ).scalar_one()
        if pending_exists:
            return {"error": "A pending battle with this opponent already exists"}, 409

        active_on_challenge = db.session.execute(
            db.select(func.count()).select_from(Battle).where(
                pair_filter,
                Battle.challenge_id == data["challenge_id"],
                Battle.status == ACTIVE,
            )
        ).scalar_one()
        if active_on_challenge:
            return {"error": "An active battle on this challenge with this opponent already exists"}, 409

        active_count = db.session.execute(
            db.select(func.count()).select_from(Battle).where(
                pair_filter,
                Battle.status == ACTIVE,
            )
        ).scalar_one()
        if active_count >= 5:
            return {"error": "Maximum of 5 active battles between two players"}, 409

        battle = Battle(
            challenge_id=data["challenge_id"],
            player1_id=uid,
            player2_id=data["opponent_id"],
            status=PENDING,
        )
        db.session.add(battle)
        db.session.commit()
        return _serialize(battle, uid), 201


class BattleChallengeListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id):
        uid = get_jwt_identity()
        opponent_id = request.args.get("opponent_id")
        if not opponent_id:
            return {"error": "opponent_id required"}, 400

        pack = db.get_or_404(ChallengePack, pack_id)
        if not pack.is_battle:
            abort(404)

        from api.resources.challenge_packs import _has_access
        if not _has_access(pack, uid):
            abort(403, error="Pack access required")

        opponent = db.session.get(User, opponent_id)
        if opponent is None:
            return {"error": "Opponent not found"}, 404
        if not _are_accepted_friends(uid, opponent_id):
            abort(403)

        challenges = db.session.execute(
            db.select(Challenge)
            .where(
                Challenge.pack_id == pack_id,
                Challenge.is_active == True,
                Challenge.sticker.is_not(None),
            )
            .order_by(Challenge.position)
        ).scalars().all()
        completed_ids = _completed_battle_challenge_ids(pack_id, [uid, opponent_id])
        return [
            _serialize_battle_picker_challenge(c, c.id in completed_ids)
            for c in challenges
        ], 200


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

        _require_battle_challenge(battle.challenge_id, uid)

        battle.status = ACTIVE
        battle.current_turn_id = battle.player2_id
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
        content = (data.get("content") or "").strip()
        if not content:
            return {"error": "content required"}, 400

        challenge = db.session.get(Challenge, battle.challenge_id)
        if challenge is None:
            return {"error": "Challenge not found"}, 404

        user = db.session.get(User, uid)
        allowed, energy_remaining = consume_energy(user, request.remote_addr)
        if not allowed:
            return {"error": "No energy remaining. Come back tomorrow."}, 429

        prior_guesses = battle.guesses.order_by(BattleGuess.turn_number).all()
        prior = [{"content": g.content, "response_code": g.response_code} for g in prior_guesses]

        rc, raw = judge_guess(challenge.subject, content, prior)

        next_turn = len(prior_guesses)

        guess = BattleGuess(
            battle_id=battle_id,
            user_id=uid,
            content=content,
            response_code=rc,
            turn_number=next_turn + 1,
            raw_response=raw,
        )
        db.session.add(guess)

        if rc == WIN:
            battle.status = FINISHED
            battle.winner_id = uid
            battle.current_turn_id = None
        else:
            battle.current_turn_id = _other_player(battle, uid)

        db.session.commit()
        check_after_battle_guess(user, won=(rc == WIN))
        return {**_serialize_guess(guess), "energy_remaining": energy_remaining}, 201


def _serialize(battle: Battle, viewer_id: str, include_guesses: bool = False) -> dict:
    status_label = {PENDING: "pending", ACTIVE: "active", FINISHED: "finished"}
    challenge = db.session.get(Challenge, battle.challenge_id)
    pack = db.session.get(ChallengePack, challenge.pack_id) if challenge else None
    guess_count = db.session.execute(
        db.select(func.count(BattleGuess.id)).where(BattleGuess.battle_id == battle.id)
    ).scalar_one()
    player1 = {"id": battle.player1.id, "name": battle.player1.name, "username": battle.player1.name}
    player2 = {"id": battle.player2.id, "name": battle.player2.name, "username": battle.player2.name}
    pair_filter = or_(
        (Battle.player1_id == battle.player1_id) & (Battle.player2_id == battle.player2_id),
        (Battle.player1_id == battle.player2_id) & (Battle.player2_id == battle.player1_id),
    )
    head_to_head = dict(db.session.execute(
        db.select(Battle.winner_id, func.count())
        .where(pair_filter, Battle.status == FINISHED, Battle.winner_id.is_not(None))
        .group_by(Battle.winner_id)
    ).all())
    data = {
        "id": battle.id,
        "challenge_id": battle.challenge_id,
        "player1": player1,
        "player2": player2,
        "status": status_label[battle.status],
        "current_turn_id": battle.current_turn_id,
        "winner_id": battle.winner_id,
        "completed_at": utc_isoformat(battle.updated_at) if battle.status == FINISHED else None,
        "guess_count": guess_count,
        "challenge": {
            "id": challenge.id,
            "subject": challenge.subject,
            "sticker": challenge.sticker,
        } if challenge and battle.status == FINISHED else None,
        "challenge_pack": {"id": pack.id, "name": pack.name} if pack else None,
        "pack": {"id": pack.id, "name": pack.name} if pack else None,
        "difficulty": DIFFICULTY_LABEL.get(challenge.difficulty, challenge.difficulty) if challenge else None,
        "player1_score": head_to_head.get(battle.player1_id, 0),
        "player2_score": head_to_head.get(battle.player2_id, 0),
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
