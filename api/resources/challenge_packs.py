from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, asc
from sqlalchemy.exc import IntegrityError
from api import db, limiter, cache
from api.common.base_model import utc_isoformat
from api.models.challenge_pack import ChallengePack
from api.models.challenge import Challenge
from api.models.game import Game
from api.models.battle import Battle, FINISHED
from api.models.user_pack_access import UserPackAccess
from sqlalchemy import or_
from api.common.challenge_enums import (
    VALID_PACK_DIFFICULTIES, VALID_DIFFICULTIES, DIFFICULTY_LABEL,
)

_STATIC_CACHE_TTL = 6 * 3600
_PACKS_CACHE_KEY = "challenge_packs:list:public-stickers:v3"
MAX_SUBJECT_HINT_LENGTH = 160


def _pack_challenges_key(pack_id: str) -> str:
    return f"challenge_packs:challenges:public-stickers:v2:{pack_id}"


def _bust_pack_cache(pack_id: str | None = None) -> None:
    cache.delete(_PACKS_CACHE_KEY)
    cache.delete("challenge_packs:list:public-stickers:v2")
    cache.delete("challenge_packs:list:public-stickers:v1")
    cache.delete("challenge_packs:list")
    if pack_id:
        cache.delete(_pack_challenges_key(pack_id))
        cache.delete(f"challenge_packs:challenges:public-stickers:v2:{pack_id}")
        cache.delete(f"challenge_packs:challenges:public-stickers:v1:{pack_id}")
        cache.delete(f"challenge_packs:challenges:{pack_id}")


def _public_challenge_filters() -> tuple:
    return (
        Challenge.is_active == True,
        Challenge.sticker.is_not(None),
        Challenge.created_by_user_id.is_(None),
    )


def _pack_has_public_challenge(pack_id: str) -> bool:
    return db.session.execute(
        db.select(Challenge.id)
        .where(Challenge.pack_id == pack_id, *_public_challenge_filters())
        .limit(1)
    ).scalar_one_or_none() is not None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_access(pack: ChallengePack, user_id: str) -> bool:
    if db.session.execute(
        db.select(UserPackAccess).where(
            UserPackAccess.pack_id == pack.id,
            UserPackAccess.user_id == user_id,
        )
    ).scalar_one_or_none() is not None:
        return True
    if pack.is_exclusive:
        return False
    if not pack.subscription_access:
        return True
    from api.resources.subscriptions import _active_subscription
    from api.common.subscription_plans import STATUS_ACTIVE, STATUS_CANCELLED
    sub = _active_subscription(user_id)
    return sub is not None and sub.status in (STATUS_ACTIVE, STATUS_CANCELLED)


def _require_access(pack: ChallengePack, user_id: str):
    if not _has_access(pack, user_id):
        abort(403)


def _cached_packs() -> tuple[list, dict]:
    """Return cached public pack definitions and public challenge counts."""
    hit = cache.get(_PACKS_CACHE_KEY)
    if hit is not None:
        return hit
    packs = db.session.execute(
        db.select(ChallengePack)
        .join(Challenge, Challenge.pack_id == ChallengePack.id)
        .where(ChallengePack.is_active == True, *_public_challenge_filters())
        .distinct()
    ).scalars().all()
    pack_ids = [p.id for p in packs]
    total_counts = dict(db.session.execute(
        db.select(Challenge.pack_id, func.count())
        .where(Challenge.pack_id.in_(pack_ids), *_public_challenge_filters())
        .group_by(Challenge.pack_id)
    ).all()) if pack_ids else {}
    result = ([_pack_payload(pack) for pack in packs], total_counts)
    cache.set(_PACKS_CACHE_KEY, result, timeout=_STATIC_CACHE_TTL)
    return result


def _cached_challenges(pack_id: str) -> list:
    """Return cached public challenge definitions for a pack."""
    key = _pack_challenges_key(pack_id)
    hit = cache.get(key)
    if hit is not None:
        return hit
    challenges = db.session.execute(
        db.select(Challenge)
        .where(Challenge.pack_id == pack_id, *_public_challenge_filters())
        .order_by(asc(Challenge.position))
    ).scalars().all()
    payload = [_challenge_payload(challenge) for challenge in challenges]
    cache.set(key, payload, timeout=_STATIC_CACHE_TTL)
    return payload


def _pack_completion_counts(pack_ids: list[str], user_id: str) -> dict:
    game_pairs = db.session.execute(
        db.select(Challenge.pack_id, Challenge.id)
        .join(Game, Game.challenge_id == Challenge.id)
        .where(
            Challenge.pack_id.in_(pack_ids),
            *_public_challenge_filters(),
            Game.user_id == user_id,
            Game.completed_at.isnot(None),
        )
    ).all()
    battle_pairs = db.session.execute(
        db.select(Challenge.pack_id, Challenge.id)
        .join(Battle, Battle.challenge_id == Challenge.id)
        .where(
            Challenge.pack_id.in_(pack_ids),
            *_public_challenge_filters(),
            Battle.status == FINISHED,
            or_(Battle.player1_id == user_id, Battle.player2_id == user_id),
        )
    ).all()

    counts: dict = {}
    for pack_id, _challenge_id in set(game_pairs) | set(battle_pairs):
        counts[pack_id] = counts.get(pack_id, 0) + 1
    return counts


def _pack_access_by_id(packs: list[dict], user_id: str) -> dict:
    pack_ids = [pack["id"] for pack in packs]
    granted_pack_ids = {
        row[0] for row in db.session.execute(
            db.select(UserPackAccess.pack_id)
            .where(UserPackAccess.user_id == user_id, UserPackAccess.pack_id.in_(pack_ids))
        ).all()
    }

    from api.resources.subscriptions import _active_subscription
    from api.common.subscription_plans import STATUS_ACTIVE, STATUS_CANCELLED
    sub = _active_subscription(user_id)
    is_subscribed = sub is not None and sub.status in (STATUS_ACTIVE, STATUS_CANCELLED)

    access = {}
    for pack in packs:
        pack_id = pack["id"]
        if pack["is_exclusive"]:
            access[pack_id] = pack_id in granted_pack_ids
        elif not pack["subscription_access"]:
            access[pack_id] = True
        else:
            access[pack_id] = pack_id in granted_pack_ids or is_subscribed
    return access


def _completed_ids_for_pack(pack_id: str, user_id: str) -> set:
    game_rows = db.session.execute(
        db.select(Game.challenge_id)
        .join(Challenge, Challenge.id == Game.challenge_id)
        .where(
            Challenge.pack_id == pack_id,
            *_public_challenge_filters(),
            Game.user_id == user_id,
            Game.completed_at.is_not(None),
        )
    ).scalars().all()
    battle_rows = db.session.execute(
        db.select(Battle.challenge_id)
        .join(Challenge, Challenge.id == Battle.challenge_id)
        .where(
            Challenge.pack_id == pack_id,
            *_public_challenge_filters(),
            Battle.status == FINISHED,
            or_(Battle.player1_id == user_id, Battle.player2_id == user_id),
        )
    ).scalars().all()
    return set(game_rows) | set(battle_rows)



def _serialize_pack(
    p,
    total_count: int | None = None,
    completed_count: int | None = None,
    challenges: list | None = None,
    completed_ids: set | None = None,
) -> dict:
    data = {
        "id": _read(p, "id"),
        "name": _read(p, "name"),
        "description": _read(p, "description"),
        "difficulty": DIFFICULTY_LABEL.get(_read(p, "difficulty"), _read(p, "difficulty")),
        "is_active": _read(p, "is_active"),
        "subscription_access": _read(p, "subscription_access"),
        "is_exclusive": _read(p, "is_exclusive"),
        "is_battle": _read(p, "is_battle"),
        "total_count": total_count if total_count is not None else 0,
        "completed_count": completed_count if completed_count is not None else 0,
        "created_at": _read_iso(p, "created_at"),
        "updated_at": _read_iso(p, "updated_at"),
    }
    if challenges is not None:
        ids = completed_ids or set()
        data["challenges"] = [
            _serialize_challenge(c, completed=_read(c, "id") in ids)
            for c in challenges
        ]
    return data


def _serialize_challenge(c, completed: bool = False, is_locked: bool = False) -> dict:
    return {
        "id": _read(c, "id"),
        "pack_id": _read(c, "pack_id"),
        "position": _read(c, "position"),
        "difficulty": DIFFICULTY_LABEL.get(_read(c, "difficulty"), _read(c, "difficulty")),
        "is_active": _read(c, "is_active"),
        "completed": completed,
        "is_locked": is_locked,
        "subject": _read(c, "subject") if completed else None,
        "subject_hint": _read(c, "subject_hint") if completed else None,
        "sticker": _read(c, "sticker") if completed else None,
        "created_at": _read_iso(c, "created_at"),
        "updated_at": _read_iso(c, "updated_at"),
    }


def _pack_payload(pack: ChallengePack) -> dict:
    return {
        "id": pack.id,
        "name": pack.name,
        "description": pack.description,
        "difficulty": pack.difficulty,
        "is_active": pack.is_active,
        "subscription_access": pack.subscription_access,
        "is_exclusive": pack.is_exclusive,
        "is_battle": pack.is_battle,
        "created_at": utc_isoformat(pack.created_at),
        "updated_at": utc_isoformat(pack.updated_at),
    }


def _challenge_payload(challenge: Challenge) -> dict:
    return {
        "id": challenge.id,
        "pack_id": challenge.pack_id,
        "position": challenge.position,
        "difficulty": challenge.difficulty,
        "is_active": challenge.is_active,
        "subject": challenge.subject,
        "subject_hint": challenge.subject_hint,
        "sticker": challenge.sticker,
        "created_at": utc_isoformat(challenge.created_at),
        "updated_at": utc_isoformat(challenge.updated_at),
    }


def _read(item, field: str):
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field)


def _read_iso(item, field: str) -> str | None:
    value = _read(item, field)
    if isinstance(value, str) or value is None:
        return value
    return utc_isoformat(value)


def _subject_hint_from_payload(data: dict) -> str | None:
    if "subject_hint" not in data:
        return None
    hint = data.get("subject_hint")
    if hint is None:
        return None
    hint = str(hint).strip()
    if len(hint) > MAX_SUBJECT_HINT_LENGTH:
        abort(400, error=f"subject_hint must be {MAX_SUBJECT_HINT_LENGTH} characters or fewer")
    return hint or None


# ── Pack list / create ────────────────────────────────────────────────────────

class ChallengePackListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        uid = get_jwt_identity()
        packs, total_counts = _cached_packs()
        if not packs:
            return [], 200

        pack_ids = [p["id"] for p in packs]
        completed_counts = _pack_completion_counts(pack_ids, uid)
        access_by_id = _pack_access_by_id(packs, uid)

        # Completed challenges per pack for this user — Games + finished Battles
        # Packs the user has explicit access to — 1 query
        # Subscription check — 1 query
        result = []
        for p in packs:
            pack_id = p["id"]
            result.append({
                **_serialize_pack(
                    p,
                    total_count=total_counts.get(pack_id, 0),
                    completed_count=completed_counts.get(pack_id, 0),
                ),
                "is_locked": not access_by_id.get(pack_id, False),
            })
        return result, 200

    def post(self):
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("name", "difficulty") if data.get(f) is None]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400
        if data["difficulty"] not in VALID_PACK_DIFFICULTIES:
            return {"error": f"difficulty must be one of {sorted(VALID_PACK_DIFFICULTIES)}"}, 400

        pack = ChallengePack(
            name=data["name"],
            description=data.get("description"),
            difficulty=data["difficulty"],
            is_active=data.get("is_active", True),
            is_battle=bool(data.get("is_battle", False)),
        )
        db.session.add(pack)
        db.session.commit()
        _bust_pack_cache()
        return _serialize_pack(pack), 201


# ── Pack detail / update / delete ─────────────────────────────────────────────

class ChallengePackResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        if not _pack_has_public_challenge(pack_id):
            abort(404)
        _require_access(pack, uid)
        challenges = _cached_challenges(pack_id)
        completed_ids = _completed_ids_for_pack(pack_id, uid)
        return _serialize_pack(
            pack,
            total_count=len(challenges),
            completed_count=len(completed_ids),
            challenges=challenges,
            completed_ids=completed_ids,
        ), 200

    def put(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        data = request.get_json(silent=True) or {}
        if "name" in data:
            pack.name = data["name"]
        if "description" in data:
            pack.description = data["description"]
        if "difficulty" in data:
            if data["difficulty"] not in VALID_PACK_DIFFICULTIES:
                return {"error": f"difficulty must be one of {sorted(VALID_PACK_DIFFICULTIES)}"}, 400
            pack.difficulty = data["difficulty"]
        if "is_active" in data:
            pack.is_active = bool(data["is_active"])
        if "is_battle" in data:
            pack.is_battle = bool(data["is_battle"])
        db.session.commit()
        _bust_pack_cache(pack_id)
        return _serialize_pack(pack), 200

    def delete(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        db.session.delete(pack)
        db.session.commit()
        _bust_pack_cache(pack_id)
        return {}, 204


# ── Challenges within a pack ──────────────────────────────────────────────────

class ChallengeListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        if not _pack_has_public_challenge(pack_id):
            abort(404)
        _require_access(pack, uid)
        challenges = _cached_challenges(pack_id)
        completed_ids = _completed_ids_for_pack(pack_id, uid)
        return [
            _serialize_challenge(c, completed=c["id"] in completed_ids)
            for c in challenges
        ], 200

    def post(self, pack_id):
        pack = db.get_or_404(ChallengePack, pack_id)
        data = request.get_json(silent=True) or {}
        missing = [f for f in ("subject", "difficulty") if data.get(f) is None]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400
        if data["difficulty"] not in VALID_DIFFICULTIES:
            return {"error": f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}"}, 400
        subject_hint = _subject_hint_from_payload(data)

        next_position = db.session.execute(
            db.select(func.coalesce(func.max(Challenge.position) + 1, 0))
            .where(Challenge.pack_id == pack.id)
        ).scalar_one()
        challenge = Challenge(
            pack_id=pack.id,
            subject=data["subject"],
            subject_hint=subject_hint,
            difficulty=data["difficulty"],
            is_active=data.get("is_active", True),
            sticker=data.get("sticker"),
            position=data.get("position", next_position),
        )
        db.session.add(challenge)
        db.session.commit()
        _bust_pack_cache(pack_id)
        return _serialize_challenge(challenge), 201


class ChallengeResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self, pack_id, challenge_id):
        uid = get_jwt_identity()
        pack = db.get_or_404(ChallengePack, pack_id)
        if not _pack_has_public_challenge(pack_id):
            abort(404)
        _require_access(pack, uid)
        challenge = _get_challenge(pack_id, challenge_id, require_public=True)
        completed = db.session.execute(
            db.select(Game).where(
                Game.challenge_id == challenge_id,
                Game.user_id == uid,
                Game.completed_at.is_not(None),
            )
        ).scalar_one_or_none() is not None
        return _serialize_challenge(challenge, completed=completed), 200

    def put(self, pack_id, challenge_id):
        challenge = _get_challenge(pack_id, challenge_id)
        data = request.get_json(silent=True) or {}
        if "subject" in data:
            challenge.subject = data["subject"]
        if "subject_hint" in data:
            challenge.subject_hint = _subject_hint_from_payload(data)
        if "difficulty" in data:
            if data["difficulty"] not in VALID_DIFFICULTIES:
                return {"error": f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}"}, 400
            challenge.difficulty = data["difficulty"]
        if "is_active" in data:
            challenge.is_active = bool(data["is_active"])
        if "sticker" in data:
            challenge.sticker = data.get("sticker")
        db.session.commit()
        _bust_pack_cache(pack_id)
        return _serialize_challenge(challenge), 200

    def delete(self, pack_id, challenge_id):
        challenge = _get_challenge(pack_id, challenge_id)
        db.session.delete(challenge)
        db.session.commit()
        _bust_pack_cache(pack_id)
        return {}, 204


def _get_challenge(pack_id: str, challenge_id: str, require_public: bool = False) -> Challenge:
    filters = [Challenge.id == challenge_id, Challenge.pack_id == pack_id]
    if require_public:
        filters.extend(_public_challenge_filters())

    challenge = db.session.execute(
        db.select(Challenge).where(*filters)
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
