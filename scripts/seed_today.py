"""
Schedule today's daily challenge slots.
Pulls subjects from already-seeded packs — run seed_packs.py first.
Run from the backend directory:  python scripts/seed_today.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
from api import create_app, db
from api.models.challenge import Challenge
from api.models.daily_challenge import DailyChallenge

TODAY = date.today()

DAILY_SUBJECTS = [
    "Donald Trump",
    "kettle",
]

app = create_app()

with app.app_context():
    for subject in DAILY_SUBJECTS:
        challenge = db.session.execute(
            db.select(Challenge).where(Challenge.subject == subject)
        ).scalar_one_or_none()

        if challenge is None:
            print(f"  ! challenge not found: '{subject}' — run seed_packs.py first")
            continue

        existing_slot = db.session.execute(
            db.select(DailyChallenge).where(
                DailyChallenge.available_on == TODAY,
                DailyChallenge.difficulty == challenge.difficulty,
            )
        ).scalar_one_or_none()

        if existing_slot:
            print(f"  ~ slot already exists for difficulty={challenge.difficulty} on {TODAY}")
            continue

        db.session.add(DailyChallenge(
            challenge_id=challenge.id,
            available_on=TODAY,
            difficulty=challenge.difficulty,
        ))
        print(f"  + scheduled '{subject}' for {TODAY}")

    try:
        db.session.commit()
        print("Done.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
