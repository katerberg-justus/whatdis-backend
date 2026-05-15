"""add raw_response to battle_guesses

Revision ID: a3c5e7d91f24
Revises: ffb102f77a23
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a3c5e7d91f24'
down_revision = 'ffb102f77a23'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('battle_guesses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('raw_response', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('battle_guesses', schema=None) as batch_op:
        batch_op.drop_column('raw_response')
