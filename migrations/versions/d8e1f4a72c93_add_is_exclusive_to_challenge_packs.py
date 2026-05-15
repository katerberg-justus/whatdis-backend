"""add is_exclusive to challenge_packs

Revision ID: d8e1f4a72c93
Revises: b2c3d4e5f6a7
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd8e1f4a72c93'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'is_exclusive',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('0'),
        ))


def downgrade():
    with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
        batch_op.drop_column('is_exclusive')
