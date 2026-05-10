"""
Seed the database with bogus data for development.
Run with: flask --app api shell < seed.py
Or:       python seed.py
"""
from sqlalchemy import text
from api import create_app, db
from api.models.user import User
from api.models.friendship import Friendship, PENDING, ACCEPTED
from api.models.game import Game
from api.models.guess import Guess
from api.models.battle import Battle, ACTIVE, FINISHED
from api.models.battle_guess import BattleGuess
from api.common.response_codes import NO, YES, INDECISIVE, REFUSAL, WIN


def uuid7():
    return db.session.execute(text("SELECT UUID_V7()")).scalar()


def run():
    app = create_app()
    with app.app_context():
        # ── Wipe existing seed data ───────────────────────────────────────
        for tbl in reversed(db.metadata.sorted_tables):
            db.session.execute(tbl.delete())
        db.session.commit()
        print("Cleared tables.")

        # ── Users ─────────────────────────────────────────────────────────
        alice   = User(id=uuid7(), name="Alice Archer",   email="alice@example.com")
        bob     = User(id=uuid7(), name="Bob Bergman",    email="bob@example.com")
        charlie = User(id=uuid7(), name="Charlie Chen",   email="charlie@example.com")
        diana   = User(id=uuid7(), name="Diana Dubois",   email="diana@example.com")
        for u, pw in [(alice, "alice123"), (bob, "bob123"), (charlie, "charlie123"), (diana, "diana123")]:
            u.set_password(pw)
        db.session.add_all([alice, bob, charlie, diana])
        db.session.flush()
        print(f"Users: {alice.id[:8]}… Alice, {bob.id[:8]}… Bob, {charlie.id[:8]}… Charlie, {diana.id[:8]}… Diana")

        # ── Friendships ───────────────────────────────────────────────────
        fs_alice_bob     = Friendship(id=uuid7(), requester_id=alice.id,   addressee_id=bob.id,     status=ACCEPTED)
        fs_alice_charlie = Friendship(id=uuid7(), requester_id=alice.id,   addressee_id=charlie.id, status=PENDING)
        fs_bob_diana     = Friendship(id=uuid7(), requester_id=bob.id,     addressee_id=diana.id,   status=ACCEPTED)
        fs_charlie_diana = Friendship(id=uuid7(), requester_id=charlie.id, addressee_id=diana.id,   status=PENDING)
        db.session.add_all([fs_alice_bob, fs_alice_charlie, fs_bob_diana, fs_charlie_diana])
        db.session.flush()
        print("Friendships seeded.")

        # ── Challenge UUIDs (placeholders — no Challenge table yet) ───────
        challenge_a = uuid7()
        challenge_b = uuid7()

        # ── Solo games ────────────────────────────────────────────────────
        game_alice = Game(id=uuid7(), challenge_id=challenge_a, user_id=alice.id)
        game_bob   = Game(id=uuid7(), challenge_id=challenge_b, user_id=bob.id)
        db.session.add_all([game_alice, game_bob])
        db.session.flush()

        # Alice's guesses (ongoing)
        db.session.add_all([
            Guess(id=uuid7(), game_id=game_alice.id, user_id=alice.id, content="Is it a living thing?",        response_code=YES),
            Guess(id=uuid7(), game_id=game_alice.id, user_id=alice.id, content="Is it larger than a cat?",     response_code=NO),
            Guess(id=uuid7(), game_id=game_alice.id, user_id=alice.id, content="Can you find it in a kitchen?",response_code=INDECISIVE),
        ])
        # Bob's guesses (won)
        db.session.add_all([
            Guess(id=uuid7(), game_id=game_bob.id, user_id=bob.id, content="Is it a person?",             response_code=YES),
            Guess(id=uuid7(), game_id=game_bob.id, user_id=bob.id, content="Is it a historical figure?",  response_code=YES),
            Guess(id=uuid7(), game_id=game_bob.id, user_id=bob.id, content="Is it Napoleon Bonaparte?",   response_code=WIN),
        ])
        db.session.flush()
        print("Solo games and guesses seeded.")

        # ── Battles ───────────────────────────────────────────────────────
        # Battle 1: Alice vs Bob — active, Alice's turn
        battle1 = Battle(
            id=uuid7(),
            challenge_id=challenge_a,
            player1_id=alice.id,
            player2_id=bob.id,
            status=ACTIVE,
            current_turn_id=alice.id,
        )
        db.session.add(battle1)
        db.session.flush()

        db.session.add_all([
            BattleGuess(id=uuid7(), battle_id=battle1.id, user_id=alice.id, content="Is it a place?",          response_code=NO,  turn_number=1),
            BattleGuess(id=uuid7(), battle_id=battle1.id, user_id=bob.id,   content="Is it a living thing?",   response_code=YES, turn_number=2),
            BattleGuess(id=uuid7(), battle_id=battle1.id, user_id=alice.id, content="Does it have four legs?", response_code=NO,  turn_number=3),
            BattleGuess(id=uuid7(), battle_id=battle1.id, user_id=bob.id,   content="Can it fly?",             response_code=YES, turn_number=4),
        ])

        # Battle 2: Charlie vs Diana — finished, Diana won
        battle2 = Battle(
            id=uuid7(),
            challenge_id=challenge_b,
            player1_id=charlie.id,
            player2_id=diana.id,
            status=FINISHED,
            current_turn_id=None,
            winner_id=diana.id,
        )
        db.session.add(battle2)
        db.session.flush()

        db.session.add_all([
            BattleGuess(id=uuid7(), battle_id=battle2.id, user_id=charlie.id, content="Is it a concept?",         response_code=NO,      turn_number=1),
            BattleGuess(id=uuid7(), battle_id=battle2.id, user_id=diana.id,   content="Is it a real person?",     response_code=YES,     turn_number=2),
            BattleGuess(id=uuid7(), battle_id=battle2.id, user_id=charlie.id, content="Is it a politician?",      response_code=REFUSAL, turn_number=3),
            BattleGuess(id=uuid7(), battle_id=battle2.id, user_id=diana.id,   content="Is it Marie Curie?",       response_code=WIN,     turn_number=4),
        ])

        db.session.commit()
        print("Battles and battle guesses seeded.")
        print("\nDone. Credentials: <email> / <name>123  e.g. alice@example.com / alice123")


if __name__ == "__main__":
    run()
