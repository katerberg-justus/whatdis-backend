"""
Sync static challenge and achievement content into the configured Flask DB.

Run after migrations in prod:
    python scripts/sync_static_content.py

Use --prune to deactivate challenge packs/challenges that are no longer present
in the seed file.
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


def _get_pack_by_name(name: str) -> ChallengePack | None:
    return db.session.execute(
        db.select(ChallengePack).where(ChallengePack.name == name)
    ).scalar_one_or_none()


def _get_challenge(pack_id: str, subject: str) -> Challenge | None:
    return db.session.execute(
        db.select(Challenge).where(
            Challenge.pack_id == pack_id,
            Challenge.subject == subject,
        )
    ).scalar_one_or_none()


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


def _sync_packs(payload: dict, prune: bool) -> tuple[int, int, int, set[str]]:
    pack_count = 0
    challenge_count = 0
    changed = 0
    active_pack_names = set()
    active_challenge_keys = set()
    touched_pack_ids = set()

    for pack_data in payload.get("challenge_packs", []):
        active_pack_names.add(pack_data["name"])
        pack = _get_pack_by_name(pack_data["name"])
        if pack is None:
            pack = ChallengePack(name=pack_data["name"])
            db.session.add(pack)
            db.session.flush()
            changed += 1

        pack.description = pack_data.get("description")
        pack.difficulty = _normalized_pack_difficulty(pack_data)
        pack.is_active = pack_data.get("is_active", True)
        pack.subscription_access = pack_data.get("subscription_access", True)
        touched_pack_ids.add(pack.id)
        pack_count += 1

        for challenge_data in pack_data.get("challenges", []):
            key = (pack_data["name"], challenge_data["subject"])
            active_challenge_keys.add(key)
            challenge = _get_challenge(pack.id, challenge_data["subject"])
            if challenge is None:
                challenge = Challenge(
                    pack_id=pack.id,
                    subject=challenge_data["subject"],
                )
                db.session.add(challenge)
                changed += 1

            challenge.difficulty = challenge_data["difficulty"]
            challenge.is_active = challenge_data.get("is_active", True)
            challenge.icon = challenge_data.get("icon")
            challenge.position = challenge_data.get("position", 0)
            challenge_count += 1

    if prune:
        existing_packs = db.session.execute(db.select(ChallengePack)).scalars()
        for pack in existing_packs:
            if pack.name not in active_pack_names and pack.is_active:
                pack.is_active = False
                touched_pack_ids.add(pack.id)

        existing_challenges = db.session.execute(
            db.select(Challenge, ChallengePack.name)
            .join(ChallengePack, ChallengePack.id == Challenge.pack_id)
        ).all()
        for challenge, pack_name in existing_challenges:
            if (pack_name, challenge.subject) not in active_challenge_keys and challenge.is_active:
                challenge.is_active = False
                touched_pack_ids.add(challenge.pack_id)

    return pack_count, challenge_count, changed, touched_pack_ids


def _sync_achievements(payload: dict) -> tuple[int, int]:
    achievement_count = 0
    changed = 0

    for data in payload.get("achievements", []):
        achievement = db.session.execute(
            db.select(Achievement).where(Achievement.name == data["name"])
        ).scalar_one_or_none()
        if achievement is None:
            achievement = Achievement(name=data["name"])
            db.session.add(achievement)
            changed += 1

        achievement.description = data["description"]
        achievement.category = data["category"]
        achievement.threshold = data["threshold"]
        achievement.icon = data.get("icon")
        achievement_count += 1

    return achievement_count, changed


def _sync_daily_challenges(payload: dict) -> int:
    daily_count = 0
    seen_slots = set()

    for data in payload.get("daily_challenges", []):
        payload_key = (data["available_on"], data["difficulty"])
        if payload_key in seen_slots:
            raise ValueError(
                f"Duplicate daily slot in seed file: {data['available_on']} "
                f"difficulty={data['difficulty']}"
            )
        seen_slots.add(payload_key)

        pack = _get_pack_by_name(data["pack_name"])
        if pack is None:
            raise ValueError(f"Daily challenge pack not found: {data['pack_name']}")

        challenge = _get_challenge(pack.id, data["subject"])
        if challenge is None:
            raise ValueError(
                f"Daily challenge subject not found in {data['pack_name']}: {data['subject']}"
            )

        available_on = date.fromisoformat(data["available_on"])
        slots = db.session.execute(
            db.select(DailyChallenge).where(
                DailyChallenge.available_on == available_on,
                DailyChallenge.difficulty == data["difficulty"],
            )
        ).scalars().all()
        slot = slots[0] if slots else None
        if slot is None:
            slot = DailyChallenge(
                available_on=available_on,
                difficulty=data["difficulty"],
            )
            db.session.add(slot)

        slot.challenge_id = challenge.id
        daily_count += 1

    return daily_count


def _clear_static_cache(touched_pack_ids: set[str]) -> None:
    cache.delete("challenge_packs:list")
    for pack_id in touched_pack_ids:
        cache.delete(f"challenge_packs:challenges:{pack_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()

    payload = _load_payload(args.input)
    app = create_app()

    with app.app_context():
        try:
            pack_count, challenge_count, pack_changes, touched_pack_ids = _sync_packs(
                payload,
                prune=args.prune,
            )
            achievement_count, achievement_changes = _sync_achievements(payload)
            daily_count = _sync_daily_challenges(payload)
            db.session.commit()
            _clear_static_cache(touched_pack_ids)
        except Exception:
            db.session.rollback()
            raise

    print(
        "Synced "
        f"{pack_count} packs, "
        f"{challenge_count} challenges, "
        f"{daily_count} daily slots, "
        f"{achievement_count} achievements "
        f"({pack_changes + achievement_changes} created)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
