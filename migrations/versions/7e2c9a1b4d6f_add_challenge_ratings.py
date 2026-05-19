"""add challenge ratings

Revision ID: 7e2c9a1b4d6f
Revises: 6c2f8d91a4b0
Create Date: 2026-05-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = '7e2c9a1b4d6f'
down_revision = '6c2f8d91a4b0'
branch_labels = None
depends_on = None


def upgrade():
    if _table_exists('challenge_ratings'):
        return

    op.create_table(
        'challenge_ratings',
        sa.Column('id', mysql.CHAR(length=36), nullable=False, server_default=sa.text('UUID_V7()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('challenge_id', mysql.CHAR(length=36), nullable=False),
        sa.Column('liked', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'challenge_id', name='uq_challenge_rating_user_challenge'),
    )
    op.create_index('ix_challenge_ratings_challenge_id', 'challenge_ratings', ['challenge_id'])
    op.create_index('ix_challenge_ratings_challenge_liked', 'challenge_ratings', ['challenge_id', 'liked'])
    op.create_index('ix_challenge_ratings_user_id', 'challenge_ratings', ['user_id'])


def downgrade():
    if not _table_exists('challenge_ratings'):
        return

    op.drop_index('ix_challenge_ratings_user_id', table_name='challenge_ratings')
    op.drop_index('ix_challenge_ratings_challenge_liked', table_name='challenge_ratings')
    op.drop_index('ix_challenge_ratings_challenge_id', table_name='challenge_ratings')
    op.drop_table('challenge_ratings')


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()
