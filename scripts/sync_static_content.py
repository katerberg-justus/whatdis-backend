"""
Sync static challenge and achievement content into the configured Flask DB.

Run after migrations in prod:
    python scripts/sync_static_content.py

The sync is strictly ID-based and incremental: every resource in the seed file
must carry an ``id``. Rows are inserted when the ID is new and updated only
when one of the tracked attributes has changed. Rows that exist in the DB but
are absent from the seed file are left untouched.
"""
import argparse
from datetime import date
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import cache, create_app, db
from api.common.challenge_enums import MIXED_DIFFICULTY
from api.models.achievement import Achievement
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.daily_challenge import DailyChallenge


DEFAULT_INPUT = os.path.join("data", "static_content.json")


def _load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported static content version: {payload.get('version')}")
    return payload


def _require_id(data: dict, kind: str) -> str:
    resource_id = data.get("id")
    if not resource_id:
        raise ValueError(f"{kind} entry missing required 'id': {data!r}")
    return resource_id


def _optional_id(data: dict) -> str | None:
    return data.get("id") or None


def _apply_changes(instance, values: dict) -> bool:
    changed = False
    for attr, new_value in values.items():
        if getattr(instance, attr) != new_value:
            setattr(instance, attr, new_value)
            changed = True
    return changed


def _normalized_pack_difficulty(pack_data: dict) -> int:
    if pack_data.get("difficulty") is not None:
        return int(pack_data["difficulty"])

    challenge_difficulties = {
        int(challenge["difficulty"])
        for challenge in pack_data.get("challenges", [])
        if challenge.get("difficulty") is not None
    }
    if len(challenge_difficulties) == 1:
        return next(iter(challenge_difficulties))
    return MIXED_DIFFICULTY


def _sync_packs(payload: dict) -> tuple[int, int, int, set[str]]:
    inserted = 0
    updated = 0
    challenge_total = 0
    touched_pack_ids: set[str] = set()

    for pack_data in payload.get("challenge_packs", []):
        pack_id = _require_id(pack_data, "challenge_pack")
        pack = db.session.get(ChallengePack, pack_id)
        pack_values = dict(
            name=pack_data["name"],
            description=pack_data.get("description"),
            difficulty=_normalized_pack_difficulty(pack_data),
            is_active=pack_data.get("is_active", True),
            subscription_access=pack_data.get("subscription_access", True),
            is_exclusive=pack_data.get("is_exclusive", False),
            is_battle=pack_data.get("is_battle", False),
        )

        if pack is None:
            pack = ChallengePack(id=pack_id, **pack_values)
            db.session.add(pack)
            db.session.flush()
            inserted += 1
            touched_pack_ids.add(pack_id)
        elif _apply_changes(pack, pack_values):
            updated += 1
            touched_pack_ids.add(pack_id)

        for challenge_data in pack_data.get("challenges", []):
            challenge_id = _optional_id(challenge_data)
            if challenge_id is None:
                continue

            challenge = db.session.get(Challenge, challenge_id)
            challenge_values = dict(
                pack_id=pack_id,
                subject=challenge_data["subject"],
                subject_hint=challenge_data.get("subject_hint"),
                difficulty=challenge_data["difficulty"],
                is_active=challenge_data.get("is_active", True),
                sticker=challenge_data.get("sticker"),
                position=challenge_data.get("position", 0),
            )

            if challenge is None:
                challenge = Challenge(id=challenge_id, **challenge_values)
                db.session.add(challenge)
                inserted += 1
                touched_pack_ids.add(pack_id)
            elif _apply_changes(challenge, challenge_values):
                updated += 1
                touched_pack_ids.add(pack_id)
            challenge_total += 1

    return inserted, updated, challenge_total, touched_pack_ids


def _sync_achievements(payload: dict) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    total = 0

    for data in payload.get("achievements", []):
        achievement_id = _optional_id(data)
        if achievement_id is None:
            continue

        achievement = db.session.get(Achievement, achievement_id)
        values = dict(
            name=data["name"],
            description=data["description"],
            category=data["category"],
            threshold=data["threshold"],
            icon=data.get("icon"),
        )

        if achievement is None:
            db.session.add(Achievement(id=achievement_id, **values))
            inserted += 1
        elif _apply_changes(achievement, values):
            updated += 1
        total += 1

    return inserted, updated, total


def _sync_daily_challenges(payload: dict) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    total = 0
    seen_slots: set[tuple[str, int]] = set()

    for data in payload.get("daily_challenges", []):
        slot_id = _optional_id(data)
        if slot_id is None:
            continue

        slot_key = (data["available_on"], data["difficulty"])
        if slot_key in seen_slots:
            raise ValueError(
                f"Duplicate daily slot in seed file: {data['available_on']} "
                f"difficulty={data['difficulty']}"
            )
        seen_slots.add(slot_key)

        challenge_id = data["challenge_id"]
        if db.session.get(Challenge, challenge_id) is None:
            raise ValueError(f"Daily challenge references unknown challenge id: {challenge_id}")

        values = dict(
            challenge_id=challenge_id,
            available_on=date.fromisoformat(data["available_on"]),
            difficulty=data["difficulty"],
        )

        slot = db.session.get(DailyChallenge, slot_id)
        if slot is None:
            db.session.add(DailyChallenge(id=slot_id, **values))
            inserted += 1
        elif _apply_changes(slot, values):
            updated += 1
        total += 1

    return inserted, updated, total


def _clear_static_cache(touched_pack_ids: set[str]) -> None:
    if not touched_pack_ids:
        return
    cache.delete("challenge_packs:list")
    cache.delete("challenge_packs:list:public-stickers:v1")
    cache.delete("challenge_packs:list:public-stickers:v2")
    for pack_id in touched_pack_ids:
        cache.delete(f"challenge_packs:challenges:{pack_id}")
        cache.delete(f"challenge_packs:challenges:public-stickers:v1:{pack_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    args = parser.parse_args()

    payload = _load_payload(args.input)
    app = create_app()

    with app.app_context():
        try:
            pack_inserted, pack_updated, challenge_total, touched_pack_ids = _sync_packs(payload)
            ach_inserted, ach_updated, ach_total = _sync_achievements(payload)
            daily_inserted, daily_updated, daily_total = _sync_daily_challenges(payload)
            db.session.commit()
            _clear_static_cache(touched_pack_ids)
        except Exception:
            db.session.rollback()
            raise

    print(
        "Synced "
        f"{challenge_total} challenges, "
        f"{daily_total} daily slots, "
        f"{ach_total} achievements "
        f"(inserted: {pack_inserted + ach_inserted + daily_inserted}, "
        f"updated: {pack_updated + ach_updated + daily_updated})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
