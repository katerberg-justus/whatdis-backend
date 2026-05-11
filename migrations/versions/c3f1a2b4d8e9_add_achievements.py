"""add achievements

Revision ID: c3f1a2b4d8e9
Revises: 8d3979b85f71
Create Date: 2026-05-11 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3f1a2b4d8e9'
down_revision = '8d3979b85f71'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'achievements',
        sa.Column('id', sa.CHAR(36), server_default=sa.text('UUID_V7()'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_achievements_category', 'achievements', ['category'])
    op.create_index('ix_achievements_category_threshold', 'achievements', ['category', 'threshold'])

    op.create_table(
        'user_achievements',
        sa.Column('id', sa.CHAR(36), server_default=sa.text('UUID_V7()'), nullable=False),
        sa.Column('user_id', sa.CHAR(36), nullable=False),
        sa.Column('achievement_id', sa.CHAR(36), nullable=False),
        sa.Column('earned_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),
    )
    op.create_index('ix_user_achievements_user_id', 'user_achievements', ['user_id'])
    op.create_index('ix_user_achievements_achievement_id', 'user_achievements', ['achievement_id'])

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('streak_updated_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('streak_updated_date')
        batch_op.drop_column('current_streak')

    op.drop_table('user_achievements')
    op.drop_table('achievements')
