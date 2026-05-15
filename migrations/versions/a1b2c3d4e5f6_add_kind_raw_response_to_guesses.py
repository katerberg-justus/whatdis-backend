"""add kind and raw_response to guesses

Revision ID: a1b2c3d4e5f6
Revises: 4a7d2c91b5e8
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '4a7d2c91b5e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('guesses', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('kind', sa.String(length=16), nullable=False, server_default='guess')
        )
        batch_op.add_column(sa.Column('raw_response', sa.Text(), nullable=True))
        batch_op.alter_column('response_code', existing_type=sa.SmallInteger(), nullable=True)


def downgrade():
    with op.batch_alter_table('guesses', schema=None) as batch_op:
        batch_op.alter_column('response_code', existing_type=sa.SmallInteger(), nullable=False)
        batch_op.drop_column('raw_response')
        batch_op.drop_column('kind')
