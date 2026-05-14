"""add sticker to challenges

Revision ID: 187928bf31e6
Revises: 95264a11ee35
Create Date: 2026-05-14 11:54:48.890356

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '187928bf31e6'
down_revision = '95264a11ee35'
branch_labels = None
depends_on = None


def upgrade():
    if not _column_exists('challenges', 'sticker'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.add_column(sa.Column('sticker', sa.Text(), nullable=True))


def downgrade():
    if _column_exists('challenges', 'sticker'):
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.drop_column('sticker')


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        column.get('name') == column_name
        for column in inspector.get_columns(table_name)
    )
