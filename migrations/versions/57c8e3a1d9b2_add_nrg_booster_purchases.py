"""add nrg booster purchases

Revision ID: 57c8e3a1d9b2
Revises: 0d42c981e7b6
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '57c8e3a1d9b2'
down_revision = '0d42c981e7b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('energy_boost', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'user_energy_purchases',
        sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('booster_id', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('energy_boost', sa.Integer(), nullable=False),
        sa.Column('id', mysql.CHAR(length=36), server_default=sa.text('UUID_V7()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_energy_purchases_stripe_checkout_session_id'), 'user_energy_purchases', ['stripe_checkout_session_id'], unique=True)
    op.create_index(op.f('ix_user_energy_purchases_stripe_customer_id'), 'user_energy_purchases', ['stripe_customer_id'], unique=False)
    op.create_index(op.f('ix_user_energy_purchases_stripe_payment_intent_id'), 'user_energy_purchases', ['stripe_payment_intent_id'], unique=False)
    op.create_index('ix_user_energy_purchases_user_created', 'user_energy_purchases', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_user_energy_purchases_user_id'), 'user_energy_purchases', ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('energy_boost', server_default=None)


def downgrade():
    op.drop_index(op.f('ix_user_energy_purchases_user_id'), table_name='user_energy_purchases')
    op.drop_index('ix_user_energy_purchases_user_created', table_name='user_energy_purchases')
    op.drop_index(op.f('ix_user_energy_purchases_stripe_payment_intent_id'), table_name='user_energy_purchases')
    op.drop_index(op.f('ix_user_energy_purchases_stripe_customer_id'), table_name='user_energy_purchases')
    op.drop_index(op.f('ix_user_energy_purchases_stripe_checkout_session_id'), table_name='user_energy_purchases')
    op.drop_table('user_energy_purchases')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('energy_boost')
