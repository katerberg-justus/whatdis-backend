"""add user achievement counters

Revision ID: f6a7b8c9d0e1
Revises: c4d5e6f7a8b9
Create Date: 2026-05-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


COUNTER_COLUMNS = (
    'total_guess_count',
    'win_count',
    'battle_win_count',
    'battle_played_count',
    'daily_completion_count',
)


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('total_guess_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('win_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('battle_win_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('battle_played_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('daily_completion_count', sa.Integer(), nullable=False, server_default='0'))

    op.execute("""
        UPDATE users u
        SET total_guess_count =
            COALESCE((SELECT COUNT(*) FROM guesses g WHERE g.user_id = u.id), 0) +
            COALESCE((SELECT COUNT(*) FROM battle_guesses bg WHERE bg.user_id = u.id), 0),
            win_count = COALESCE((
                SELECT COUNT(*)
                FROM games g
                WHERE g.user_id = u.id
                  AND g.completed_at IS NOT NULL
            ), 0),
            battle_win_count = COALESCE((
                SELECT COUNT(*)
                FROM battles b
                WHERE b.winner_id = u.id
            ), 0),
            battle_played_count = COALESCE((
                SELECT COUNT(*)
                FROM battles b
                WHERE b.status = 2
                  AND (b.player1_id = u.id OR b.player2_id = u.id)
            ), 0),
            daily_completion_count = COALESCE((
                SELECT COUNT(*)
                FROM games g
                WHERE g.user_id = u.id
                  AND g.completed_at IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM daily_challenges dc
                      WHERE dc.challenge_id = g.challenge_id
                  )
            ), 0)
    """)


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        for column in reversed(COUNTER_COLUMNS):
            batch_op.drop_column(column)
