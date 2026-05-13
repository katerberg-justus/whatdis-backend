"""drop challenge_type from challenges, challenge_packs, daily_challenges

Revision ID: f2a8c1d3e4b5
Revises: d1f3b9a2c705
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = 'f2a8c1d3e4b5'
down_revision = 'd1f3b9a2c705'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.drop_column('challenge_type')

    with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
        batch_op.drop_column('challenge_type')

    with op.batch_alter_table('daily_challenges', schema=None) as batch_op:
        batch_op.drop_constraint('uq_daily_slot', type_='unique')
        batch_op.drop_column('challenge_type')
        batch_op.create_unique_constraint('uq_daily_slot', ['available_on', 'difficulty'])


def downgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'challenge_type', mysql.TINYINT(unsigned=True), nullable=True,
        ))

    with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'challenge_type', mysql.TINYINT(unsigned=True), nullable=True,
        ))

    with op.batch_alter_table('daily_challenges', schema=None) as batch_op:
        batch_op.drop_constraint('uq_daily_slot', type_='unique')
        batch_op.add_column(sa.Column(
            'challenge_type', mysql.TINYINT(unsigned=True), nullable=True,
        ))
        batch_op.create_unique_constraint(
            'uq_daily_slot', ['available_on', 'challenge_type', 'difficulty'],
        )
