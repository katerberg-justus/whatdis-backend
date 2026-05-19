"""add user identities

Revision ID: d4f1c2a8b6e9
Revises: 7e2c9a1b4d6f
Create Date: 2026-05-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'd4f1c2a8b6e9'
down_revision = '7e2c9a1b4d6f'
branch_labels = None
depends_on = None


def upgrade():
    if _table_exists('user_identities'):
        return

    op.create_table(
        'user_identities',
        sa.Column('id', mysql.CHAR(length=36), nullable=False, server_default=sa.text('UUID_V7()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'subject', name='uq_user_identities_provider_subject'),
    )
    op.create_index('ix_user_identities_user_id', 'user_identities', ['user_id'])
    op.create_index('ix_user_identities_user_id_provider', 'user_identities', ['user_id', 'provider'])


def downgrade():
    if not _table_exists('user_identities'):
        return
    op.drop_index('ix_user_identities_user_id_provider', table_name='user_identities')
    op.drop_index('ix_user_identities_user_id', table_name='user_identities')
    op.drop_table('user_identities')


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()
