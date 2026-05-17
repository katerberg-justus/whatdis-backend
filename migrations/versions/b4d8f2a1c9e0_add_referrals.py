"""add referrals

Revision ID: b4d8f2a1c9e0
Revises: a2b3c4d5e6f7
Create Date: 2026-05-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'b4d8f2a1c9e0'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('referral_code', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('referrer_id', mysql.CHAR(length=36), nullable=True))
        batch_op.add_column(sa.Column('referral_signup_bonus_awarded', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('referral_referrer_bonus_awarded', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.create_index(batch_op.f('ix_users_referral_code'), ['referral_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_referrer_id'), ['referrer_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_users_referrer_id_users',
            'users',
            ['referrer_id'],
            ['id'],
            ondelete='SET NULL',
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('referral_signup_bonus_awarded', server_default=None)
        batch_op.alter_column('referral_referrer_bonus_awarded', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_referrer_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_users_referrer_id'))
        batch_op.drop_index(batch_op.f('ix_users_referral_code'))
        batch_op.drop_column('referral_referrer_bonus_awarded')
        batch_op.drop_column('referral_signup_bonus_awarded')
        batch_op.drop_column('referrer_id')
        batch_op.drop_column('referral_code')
