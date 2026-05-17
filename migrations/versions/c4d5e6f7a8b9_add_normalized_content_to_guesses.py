"""add normalized_content to guesses

Revision ID: c4d5e6f7a8b9
Revises: 57c8e3a1d9b2
Create Date: 2026-05-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7a8b9'
down_revision = '57c8e3a1d9b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('guesses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('normalized_content', sa.String(length=160), nullable=True))
        batch_op.create_index(
            'ix_guesses_normalized_kind_response_game',
            ['normalized_content', 'kind', 'response_code', 'game_id'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('guesses', schema=None) as batch_op:
        batch_op.drop_index('ix_guesses_normalized_kind_response_game')
        batch_op.drop_column('normalized_content')
