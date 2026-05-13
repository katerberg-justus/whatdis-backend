"""add currency to users

Revision ID: 9f4b7a6c2d31
Revises: 54456d40025d
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9f4b7a6c2d31'
down_revision = '54456d40025d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('currency')
