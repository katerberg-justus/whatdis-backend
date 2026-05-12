"""
Seed all achievements.
Run from the backend directory:  python scripts/seed_achievements.py
Re-running is safe — existing achievements (matched by name) are skipped.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import create_app, db
from api.models.achievement import Achievement

ACHIEVEMENTS = [
    # ── Guesses ──────────────────────────────────────────────────────────────
    {
        "category": "guesses", "threshold": 1,
        "name": "First Whisper",
        "description": "You breathed your first question into the void. The game has begun.",
    },
    {
        "category": "guesses", "threshold": 10,
        "name": "Curious Cat",
        "description": "Ten questions down. You're getting warmer.",
    },
    {
        "category": "guesses", "threshold": 50,
        "name": "Fifty Shades of Maybe",
        "description": "Fifty guesses deep. You've tasted yes, no, and everything between.",
    },
    {
        "category": "guesses", "threshold": 100,
        "name": "Centurion of Questions",
        "description": "A hundred guesses asked. Your instincts are sharpening.",
    },
    {
        "category": "guesses", "threshold": 500,
        "name": "The Half-Millennial",
        "description": "Five hundred questions. The sphinx would fear you by now.",
    },
    {
        "category": "guesses", "threshold": 1000,
        "name": "The Grand Inquisitor",
        "description": "A thousand guesses. You have made the art of asking your own.",
    },
    {
        "category": "guesses", "threshold": 5000,
        "name": "Five Thousand Whispers",
        "description": "Five thousand questions. The universe has few secrets left from you.",
    },
    {
        "category": "guesses", "threshold": 10000,
        "name": "Decamillennial Doubter",
        "description": "Ten thousand guesses. You've questioned everything — twice.",
    },
    {
        "category": "guesses", "threshold": 50000,
        "name": "Oracle's Shadow",
        "description": "Fifty thousand questions. You walk the line between seeker and sage.",
    },
    {
        "category": "guesses", "threshold": 100000,
        "name": "The All-Questioner",
        "description": "One hundred thousand guesses. You are the question itself.",
    },

    # ── Wins ─────────────────────────────────────────────────────────────────
    {
        "category": "wins", "threshold": 1,
        "name": "First Blood",
        "description": "You named the nameless. The secret never saw you coming.",
    },
    {
        "category": "wins", "threshold": 5,
        "name": "Five-Star Detective",
        "description": "Five victories. Your instincts are beginning to sharpen.",
    },
    {
        "category": "wins", "threshold": 20,
        "name": "Pattern Weaver",
        "description": "Twenty wins. You don't just guess — you deduce.",
    },
    {
        "category": "wins", "threshold": 50,
        "name": "Mind Unlocker",
        "description": "Fifty secrets cracked. Lesser minds would have stopped long ago.",
    },
    {
        "category": "wins", "threshold": 100,
        "name": "The Centurion",
        "description": "A hundred wins. One hundred times the secret has bowed to you.",
    },
    {
        "category": "wins", "threshold": 200,
        "name": "Double Century",
        "description": "Two hundred victories. Your reputation precedes you.",
    },
    {
        "category": "wins", "threshold": 500,
        "name": "Vault Cracker",
        "description": "Five hundred mysteries solved. No secret is safe in your presence.",
    },
    {
        "category": "wins", "threshold": 1000,
        "name": "The Revealer",
        "description": "A thousand identities unmasked. You are the answer they dreaded.",
    },
    {
        "category": "wins", "threshold": 5000,
        "name": "The Omniscient",
        "description": "Five thousand wins. You have become the thing you sought.",
    },

    # ── Daily challenges ──────────────────────────────────────────────────────
    {
        "category": "daily", "threshold": 1,
        "name": "First Dawn",
        "description": "You answered the call on day one. The ritual has begun.",
    },
    {
        "category": "daily", "threshold": 5,
        "name": "Five Days Strong",
        "description": "Five daily challenges conquered. This is becoming a habit.",
    },
    {
        "category": "daily", "threshold": 20,
        "name": "Three-Week Warrior",
        "description": "Twenty daily challenges. You show up even when it's hard.",
    },
    {
        "category": "daily", "threshold": 50,
        "name": "Golden Fifty",
        "description": "Fifty daily completions. A fixture of the daily leaderboard.",
    },
    {
        "category": "daily", "threshold": 100,
        "name": "The Centurion's Call",
        "description": "A hundred daily challenges done. Rain, shine, or mystery — you're here.",
    },
    {
        "category": "daily", "threshold": 200,
        "name": "The Devoted",
        "description": "Two hundred daily challenges. What even is a rest day?",
    },
    {
        "category": "daily", "threshold": 500,
        "name": "Half-Millennium Daily",
        "description": "Five hundred daily challenges. This has become your daily bread.",
    },
    {
        "category": "daily", "threshold": 1000,
        "name": "The Faithful",
        "description": "A thousand daily challenges. Your loyalty is inscribed in the ledger.",
    },
    {
        "category": "daily", "threshold": 5000,
        "name": "Daily Deity",
        "description": "Five thousand daily challenges. The game bends to your schedule now.",
    },

    # ── Battles played ───────────────────────────────────────────────────────
    {
        "category": "battle_played", "threshold": 1,
        "name": "First Duel",
        "description": "You stepped into the arena. The crowd holds its breath.",
    },
    {
        "category": "battle_played", "threshold": 5,
        "name": "Arena Regular",
        "description": "Five battles fought. You're no longer just a visitor.",
    },
    {
        "category": "battle_played", "threshold": 20,
        "name": "Seasoned Duelist",
        "description": "Twenty battles. You know the smell of the arena well.",
    },
    {
        "category": "battle_played", "threshold": 50,
        "name": "Veteran of the Void",
        "description": "Fifty battles contested. Win or lose, you always return.",
    },
    {
        "category": "battle_played", "threshold": 100,
        "name": "Centurion of Clashes",
        "description": "A hundred battles. The arena was built for someone like you.",
    },
    {
        "category": "battle_played", "threshold": 200,
        "name": "Battle-Hardened",
        "description": "Two hundred duels. Scars don't slow you down anymore.",
    },
    {
        "category": "battle_played", "threshold": 500,
        "name": "The Relentless",
        "description": "Five hundred battles. Your opponents see your name and hesitate.",
    },
    {
        "category": "battle_played", "threshold": 1000,
        "name": "Legend of the Arena",
        "description": "A thousand battles. They'll be telling stories about you long after.",
    },

    # ── Battle wins ───────────────────────────────────────────────────────────
    {
        "category": "battle_won", "threshold": 1,
        "name": "First Conquest",
        "description": "You bested another mind. The taste of victory is yours.",
    },
    {
        "category": "battle_won", "threshold": 5,
        "name": "Five-Time Victor",
        "description": "Five opponents outwitted. You're developing a reputation.",
    },
    {
        "category": "battle_won", "threshold": 20,
        "name": "Dominant Force",
        "description": "Twenty wins. Opponents are starting to study your patterns.",
    },
    {
        "category": "battle_won", "threshold": 50,
        "name": "Champion of Fifty",
        "description": "Fifty battles won. The arena whispers your name.",
    },
    {
        "category": "battle_won", "threshold": 100,
        "name": "Uncrowned King",
        "description": "A hundred victories. The crown fits whether they give it or not.",
    },
    {
        "category": "battle_won", "threshold": 200,
        "name": "The Untouchable",
        "description": "Two hundred wins. Your opponents already know how this ends.",
    },
    {
        "category": "battle_won", "threshold": 500,
        "name": "Apex Predator",
        "description": "Five hundred duels claimed. You hunt secrets for sport.",
    },
    {
        "category": "battle_won", "threshold": 1000,
        "name": "The Unconquerable",
        "description": "A thousand battles won. There is no opponent left who doesn't fear you.",
    },

    # ── Streaks ───────────────────────────────────────────────────────────────
    {
        "category": "streak", "threshold": 2,
        "name": "Back-to-Back",
        "description": "Two days running. The flame flickers to life.",
    },
    {
        "category": "streak", "threshold": 7,
        "name": "Week Warrior",
        "description": "Seven consecutive days. A full week of showing up.",
    },
    {
        "category": "streak", "threshold": 14,
        "name": "Fortnight of Fire",
        "description": "Fourteen days straight. Two weeks of unbroken devotion.",
    },
    {
        "category": "streak", "threshold": 30,
        "name": "Monthly Master",
        "description": "Thirty consecutive days. A full month of daily dedication.",
    },
    {
        "category": "streak", "threshold": 90,
        "name": "Quarterly Legend",
        "description": "Ninety straight days. An entire quarter of unwavering resolve.",
    },
    {
        "category": "streak", "threshold": 180,
        "name": "Half-Year Hero",
        "description": "One hundred eighty days without pause. Six months of devotion.",
    },
    {
        "category": "streak", "threshold": 365,
        "name": "Year-Round Champion",
        "description": "365 consecutive days. An entire year without missing a beat.",
    },
    {
        "category": "streak", "threshold": 730,
        "name": "Biennial Titan",
        "description": "Two full years, day after day. There are no words — only reverence.",
    },
]

app = create_app()

with app.app_context():
    added = 0
    for data in ACHIEVEMENTS:
        existing = db.session.execute(
            db.select(Achievement).where(Achievement.name == data["name"])
        ).scalar_one_or_none()
        if existing:
            print(f"  ~ skipping: {data['name']}")
            continue
        db.session.add(Achievement(**data))
        print(f"  + {data['category']:8s} {data['threshold']:>7,}  {data['name']}")
        added += 1

    try:
        db.session.commit()
        print(f"\nDone. Seeded {added} achievements.")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
