"""add history query indexes

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-05-17 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a2b3c4d5e6f7'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


INDEXES = {
    "games": [
        ("ix_games_user_updated_created", ["user_id", "updated_at", "created_at"]),
        ("ix_games_user_completed_updated_created", ["user_id", "completed_at", "updated_at", "created_at"]),
    ],
    "battles": [
        ("ix_battles_player1_updated_created", ["player1_id", "updated_at", "created_at"]),
        ("ix_battles_player2_updated_created", ["player2_id", "updated_at", "created_at"]),
        ("ix_battles_player1_status_updated_created", ["player1_id", "status", "updated_at", "created_at"]),
        ("ix_battles_player2_status_updated_created", ["player2_id", "status", "updated_at", "created_at"]),
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
