"""add performance indexes

Revision ID: 0d42c981e7b6
Revises: c8d4e6f0a1b2
Create Date: 2026-05-16 13:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d42c981e7b6'
down_revision = 'c8d4e6f0a1b2'
branch_labels = None
depends_on = None


INDEXES = {
    "games": [
        ("ix_games_user_challenge", ["user_id", "challenge_id"]),
        ("ix_games_user_completed_challenge", ["user_id", "completed_at", "challenge_id"]),
    ],
    "guesses": [
        ("ix_guesses_game_kind_created", ["game_id", "kind", "created_at"]),
        ("ix_guesses_user_created_kind", ["user_id", "created_at", "kind"]),
    ],
    "battles": [
        ("ix_battles_player_pair_status", ["player1_id", "player2_id", "status"]),
        ("ix_battles_challenge_status", ["challenge_id", "status"]),
        ("ix_battles_winner", ["winner_id"]),
    ],
    "battle_guesses": [
        ("ix_battle_guesses_battle_turn", ["battle_id", "turn_number"]),
        ("ix_battle_guesses_user_created", ["user_id", "created_at"]),
    ],
    "user_subscriptions": [
        ("ix_user_subscriptions_user_status_created", ["user_id", "status", "created_at"]),
    ],
}


def upgrade():
    existing = _existing_indexes()
    for table_name, indexes in INDEXES.items():
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for index_name, columns in indexes:
                if index_name not in existing.get(table_name, set()):
                    batch_op.create_index(index_name, columns, unique=False)


def downgrade():
    existing = _existing_indexes()
    for table_name, indexes in reversed(INDEXES.items()):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            for index_name, _columns in reversed(indexes):
                if index_name in existing.get(table_name, set()):
                    batch_op.drop_index(index_name)


def _existing_indexes() -> dict[str, set[str]]:
    inspector = sa.inspect(op.get_bind())
    return {
        table_name: {index["name"] for index in inspector.get_indexes(table_name)}
        for table_name in INDEXES
    }
