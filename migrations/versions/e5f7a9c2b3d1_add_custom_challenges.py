"""add custom challenges

Revision ID: e5f7a9c2b3d1
Revises: b4d8f2a1c9e0
Create Date: 2026-05-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'e5f7a9c2b3d1'
down_revision = 'b4d8f2a1c9e0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if not _column_exists('challenge_packs', 'is_custom'):
        with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_custom', sa.Boolean(), nullable=False, server_default='0'))

    if not _column_exists('challenges', 'created_by_user_id'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.add_column(sa.Column('created_by_user_id', mysql.CHAR(length=36), nullable=True))
            batch_op.create_index(batch_op.f('ix_challenges_created_by_user_id'), ['created_by_user_id'], unique=False)
            batch_op.create_foreign_key(
                'fk_challenges_created_by_user_id_users',
                'users', ['created_by_user_id'], ['id'], ondelete='CASCADE',
            )

    if not _column_exists('challenges', 'share_token'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.add_column(sa.Column('share_token', sa.String(length=16), nullable=True))
            batch_op.create_index(batch_op.f('ix_challenges_share_token'), ['share_token'], unique=True)

    if not _table_exists('user_challenge_accesses'):
        op.create_table(
            'user_challenge_accesses',
            sa.Column('id', mysql.CHAR(length=36), nullable=False, server_default=sa.text('UUID_V7()')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('user_id', mysql.CHAR(length=36), nullable=False),
            sa.Column('challenge_id', mysql.CHAR(length=36), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('user_id', 'challenge_id', name='uq_user_challenge_access'),
        )
        op.create_index('ix_user_challenge_accesses_user_id', 'user_challenge_accesses', ['user_id'])
        op.create_index('ix_user_challenge_accesses_challenge_id', 'user_challenge_accesses', ['challenge_id'])

    existing = bind.execute(sa.text(
        "SELECT id FROM challenge_packs WHERE is_custom = 1 LIMIT 1"
    )).scalar()
    if existing is None:
        bind.execute(sa.text(
            "INSERT INTO challenge_packs (id, name, description, difficulty, "
            "is_active, subscription_access, is_exclusive, is_battle, is_custom) "
            "VALUES (UUID_V7(), 'Custom Challenges', "
            "'User-authored challenges shared via private link', 4, "
            "1, 0, 1, 0, 1)"
        ))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM challenge_packs WHERE is_custom = 1"))

    if _table_exists('user_challenge_accesses'):
        op.drop_index('ix_user_challenge_accesses_challenge_id', table_name='user_challenge_accesses')
        op.drop_index('ix_user_challenge_accesses_user_id', table_name='user_challenge_accesses')
        op.drop_table('user_challenge_accesses')

    if _column_exists('challenges', 'share_token'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_challenges_share_token'))
            batch_op.drop_column('share_token')

    if _column_exists('challenges', 'created_by_user_id'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.drop_constraint('fk_challenges_created_by_user_id_users', type_='foreignkey')
            batch_op.drop_index(batch_op.f('ix_challenges_created_by_user_id'))
            batch_op.drop_column('created_by_user_id')

    if _column_exists('challenge_packs', 'is_custom'):
        with op.batch_alter_table('challenge_packs', schema=None) as batch_op:
            batch_op.drop_column('is_custom')


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        column.get('name') == column_name
        for column in inspector.get_columns(table_name)
    )


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()
