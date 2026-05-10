from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from api import db, limiter
from api.models.challenge_pack import ChallengePack
from api.models.challenge import Challenge
from api.models.user_pack_access import UserPackAccess
from api.common.challenge_enums import (
    VALID_PACK_TYPES, VALID_PACK_DIFFICULTIES,
    VALID_CHALLENGE_TYPES, VALID_DIFFICULTIES,
    CHALLENGE_TYPE_LABEL, DIFFICULTY_LABEL,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_access(pack_id: str, user_id: str) -> bool:
    return db.session.execute(
        db.select(UserPackAccess).where(
            UserPackAccess.pack_id == pack_id,
            UserPackAccess.user_id == user_id,
        )
    ).scalar_one_or_none() is not None


def _require_access(pack: ChallengePack, user_id: str):
    if not _has_access(pack.id, user_id):
        abort(403)


def _serialize_pack(p: ChallengePack, include_challenges: bool = False) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "challenge_type": CHALLENGE_TYPE_LABEL.get(p.challenge_type, p.challenge_type),
        "difficulty": DIFFICULTY_LABEL.get(p.difficulty, p.difficulty),
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if include_challenges:
        data["challenges"] = [_serialize_challenge(c) for c in p.challenges.filter_by(is_active=True)]
    return data


def _serialize_challenge(c: Challenge) -> dict:
    return {
        "id": c.id,
        "pack_id": c.pack_id,
        "subject": c.subject,
        "challenge_type": CHALLENGE_TYPE_LABEL.get(c.challenge_type, c.challenge_type),
        "difficulty": DIFFICULTY_LABEL.get(c.difficulty, c.difficulty),
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ── Pack list / create ────────────────────────────────────────────────────────

class ChallengePackListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        accessible_pack_ids = db.session.execute(
            db.select(UserPackAccess.pack_id).where(UserPackAccess.user_id == uid)
        ).scalars().all()
        packs = db.session.execute(
            db.select(ChallengePack).where(ChallengePack.is_active == True)
        ).scalars().all()
        return [
            {**_serialize_pack(p), "has_access": p.id in accessible_pack_ids}
            for p in packs
        ], 200

    def post(self):
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("name", "challenge_type", "difficulty") if data.get(f) is None]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400
        if data["challenge_type"] not in VALID_PACK_TYPES:
            return {"error": f"challenge_type must be one of {sorted(VALID_PACK_TYPES)}"}, 400
        if data["difficulty"] not in VALID_PACK_DIFFICULTIES:
            return {"error": f"difficulty must be one of {sorted(VALID_PACK_DIFFICULTIES)}"}, 400

        pack = ChallengePack(
            name=data["name"],
            description=data.get("description"),
            challenge_type=data["challenge_type"],
            difficulty=data["difficulty"],
            is_active=data.get("is_active", True),
        )
        db.session.add(pack)
        db.session.commit()
        return _serialize_pack(pack), 201


# ── Pack detail / update / delete ─────────────────────────────────────────────

class ChallengePackResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        _require_access(pack, uid)
        return _serialize_pack(pack, include_challenges=True), 200

    def put(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        data = request.get_json(silent=True) or {}
        if "name" in data:
            pack.name = data["name"]
        if "description" in data:
            pack.description = data["description"]
        if "challenge_type" in data:
            if data["challenge_type"] not in VALID_PACK_TYPES:
                return {"error": f"challenge_type must be one of {sorted(VALID_PACK_TYPES)}"}, 400
            pack.challenge_type = data["challenge_type"]
        if "difficulty" in data:
            if data["difficulty"] not in VALID_PACK_DIFFICULTIES:
                return {"error": f"difficulty must be one of {sorted(VALID_PACK_DIFFICULTIES)}"}, 400
            pack.difficulty = data["difficulty"]
        if "is_active" in data:
            pack.is_active = bool(data["is_active"])
        db.session.commit()
        return _serialize_pack(pack), 200

    def delete(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        db.session.delete(pack)
        db.session.commit()
        return {}, 204


# ── Challenges within a pack ──────────────────────────────────────────────────

class ChallengeListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        _require_access(pack, uid)
        challenges = pack.challenges.filter_by(is_active=True).all()
        return [_serialize_challenge(c) for c in challenges], 200

    def post(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("subject", "challenge_type", "difficulty") if data.get(f) is None]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400
        if data["challenge_type"] not in VALID_CHALLENGE_TYPES:
            return {"error": f"challenge_type must be one of {sorted(VALID_CHALLENGE_TYPES)}"}, 400
        if data["difficulty"] not in VALID_DIFFICULTIES:
            return {"error": f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}"}, 400

        challenge = Challenge(
            pack_id=pack.id,
            subject=data["subject"],
            challenge_type=data["challenge_type"],
            difficulty=data["difficulty"],
            is_active=data.get("is_active", True),
        )
        db.session.add(challenge)
        db.session.commit()
        return _serialize_challenge(challenge), 201


class ChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id, challenge_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        _require_access(pack, uid)
        challenge = _get_challenge(pack_id, challenge_id)
        return _serialize_challenge(challenge), 200

    def put(self, pack_id, challenge_id):
        challenge = _get_challenge(pack_id, challenge_id)
        data = request.get_json(silent=True) or {}
        if "subject" in data:
            challenge.subject = data["subject"]
        if "challenge_type" in data:
            if data["challenge_type"] not in VALID_CHALLENGE_TYPES:
                return {"error": f"challenge_type must be one of {sorted(VALID_CHALLENGE_TYPES)}"}, 400
            challenge.challenge_type = data["challenge_type"]
        if "difficulty" in data:
            if data["difficulty"] not in VALID_DIFFICULTIES:
                return {"error": f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}"}, 400
            challenge.difficulty = data["difficulty"]
        if "is_active" in data:
            challenge.is_active = bool(data["is_active"])
        db.session.commit()
        return _serialize_challenge(challenge), 200

    def delete(self, pack_id, challenge_id):
        challenge = _get_challenge(pack_id, challenge_id)
        db.session.delete(challenge)
        db.session.commit()
        return {}, 204


def _get_challenge(pack_id: str, challenge_id: str) -> Challenge:
    challenge = db.session.execute(
        db.select(Challenge).where(
            Challenge.id == challenge_id,
            Challenge.pack_id == pack_id,
        )
    ).scalar_one_or_none()
    if challenge is None:
        abort(404)
    return challenge


# ── Pack access management ────────────────────────────────────────────────────

class PackAccessResource(Resource):
    """Grant or revoke a user's access to a pack."""
    decorators = [jwt_required(), limiter.limit("20 per minute")]

    def post(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        data = request.get_json(silent=True) or {}
        if not data.get("user_id"):
            return {"error": "user_id required"}, 400

        access = UserPackAccess(user_id=data["user_id"], pack_id=pack.id)
        db.session.add(access)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "User already has access"}, 409
        return {"pack_id": pack.id, "user_id": data["user_id"]}, 201

    def delete(self, pack_id):
        data = request.get_json(silent=True) or {}
        if not data.get("user_id"):
            return {"error": "user_id required"}, 400

        access = db.session.execute(
            db.select(UserPackAccess).where(
                UserPackAccess.pack_id == pack_id,
                UserPackAccess.user_id == data["user_id"],
            )
        ).scalar_one_or_none()
        if access is None:
            return {"error": "Access record not found"}, 404

        db.session.delete(access)
        db.session.commit()
        return {}, 204
