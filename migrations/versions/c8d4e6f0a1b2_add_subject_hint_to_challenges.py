"""add subject_hint to challenges

Revision ID: c8d4e6f0a1b2
Revises: a3c5e7d91f24
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c8d4e6f0a1b2'
down_revision = 'a3c5e7d91f24'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subject_hint', sa.String(length=160), nullable=True))


def downgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.drop_column('subject_hint')
