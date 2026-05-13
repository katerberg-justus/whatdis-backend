"""is_active default true on challenges

Revision ID: 54456d40025d
Revises: f2a8c1d3e4b5
Create Date: 2026-05-13 13:40:36.914120

"""
from alembic import op
import sqlalchemy as sa


revision = '54456d40025d'
down_revision = 'f2a8c1d3e4b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.alter_column(
            'is_active',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.text('1'),
        )


def downgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.alter_column(
            'is_active',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )
