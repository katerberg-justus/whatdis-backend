"""add push subscriptions

Revision ID: 6c2f8d91a4b0
Revises: e5f7a9c2b3d1
Create Date: 2026-05-18 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = '6c2f8d91a4b0'
down_revision = 'e5f7a9c2b3d1'
branch_labels = None
depends_on = None


def upgrade():
    if _table_exists('push_subscriptions'):
        return

    op.create_table(
        'push_subscriptions',
        sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('endpoint_hash', sa.String(length=64), nullable=False),
        sa.Column('p256dh', sa.Text(), nullable=False),
        sa.Column('auth', sa.Text(), nullable=False),
        sa.Column('content_encoding', sa.String(length=32), server_default='aes128gcm', nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('id', mysql.CHAR(length=36), server_default=sa.text('UUID_V7()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('push_subscriptions', schema=None) as batch_op:
        batch_op.create_index('ix_push_subscriptions_endpoint_hash', ['endpoint_hash'], unique=True)
        batch_op.create_index('ix_push_subscriptions_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_push_subscriptions_user_active', ['user_id', 'is_active'], unique=False)


def downgrade():
    if _table_exists('push_subscriptions'):
        op.drop_table('push_subscriptions')


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()
