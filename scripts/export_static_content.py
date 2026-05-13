"""
Export static challenge and achievement content from the configured Flask DB.

Run from the backend directory:
    python scripts/export_static_content.py

The output is intended to be committed and replayed in prod with:
    python scripts/sync_static_content.py
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import create_app, db
from api.models.achievement import Achievement
from api.models.challenge import Challenge
from api.models.challenge_pack import ChallengePack
from api.models.daily_challenge import DailyChallenge


DEFAULT_OUTPUT = os.path.join("data", "static_content.json")
VERSION = 1


def _challenge_payload(challenge: Challenge) -> dict:
    return {
        "subject": challenge.subject,
        "difficulty": int(challenge.difficulty),
        "is_active": bool(challenge.is_active),
        "icon": challenge.icon,
        "position": int(challenge.position),
    }


def _pack_payload(pack: ChallengePack) -> dict:
    challenges = db.session.execute(
        db.select(Challenge)
        .where(Challenge.pack_id == pack.id)
        .order_by(Challenge.position, Challenge.subject)
    ).scalars()

    return {
        "name": pack.name,
        "description": pack.description,
        "difficulty": int(pack.difficulty),
        "is_active": bool(pack.is_active),
        "subscription_access": bool(pack.subscription_access),
        "challenges": [_challenge_payload(challenge) for challenge in challenges],
    }


def _achievement_payload(achievement: Achievement) -> dict:
    return {
        "name": achievement.name,
        "description": achievement.description,
        "category": achievement.category,
        "threshold": int(achievement.threshold),
        "icon": achievement.icon,
    }


def _daily_payload(slot: DailyChallenge) -> dict:
    return {
        "available_on": slot.available_on.isoformat(),
        "difficulty": int(slot.difficulty),
        "pack_name": slot.challenge.pack.name,
        "subject": slot.challenge.subject,
    }


def _daily_payloads() -> tuple[list[dict], list[tuple[str, int]]]:
    slots = db.session.execute(
        db.select(DailyChallenge)
        .order_by(
            DailyChallenge.available_on,
            DailyChallenge.difficulty,
            DailyChallenge.updated_at.desc(),
            DailyChallenge.created_at.desc(),
        )
    ).scalars()

    payloads = []
    seen = set()
    duplicates = []
    for slot in slots:
        key = (slot.available_on.isoformat(), int(slot.difficulty))
        if key in seen:
            duplicates.append(key)
            continue
        seen.add(key)
        payloads.append(_daily_payload(slot))

    return payloads, duplicates


def export_static_content() -> tuple[dict, list[tuple[str, int]]]:
    packs = db.session.execute(
        db.select(ChallengePack).order_by(ChallengePack.name)
    ).scalars()
    achievements = db.session.execute(
        db.select(Achievement).order_by(Achievement.category, Achievement.threshold, Achievement.name)
    ).scalars()
    daily_challenges, duplicate_daily_slots = _daily_payloads()

    return {
        "version": VERSION,
        "challenge_packs": [_pack_payload(pack) for pack in packs],
        "achievements": [_achievement_payload(achievement) for achievement in achievements],
        "daily_challenges": daily_challenges,
    }, duplicate_daily_slots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        payload, duplicate_daily_slots = export_static_content()

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(
        "Exported "
        f"{len(payload['challenge_packs'])} packs, "
        f"{sum(len(pack['challenges']) for pack in payload['challenge_packs'])} challenges, "
        f"{len(payload['daily_challenges'])} daily slots, "
        f"{len(payload['achievements'])} achievements to {output_path}."
    )
    if duplicate_daily_slots:
        unique_duplicates = sorted(set(duplicate_daily_slots))
        print(
            "Skipped duplicate daily slots already represented in the export: "
            + ", ".join(f"{day}/difficulty={difficulty}" for day, difficulty in unique_duplicates)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
