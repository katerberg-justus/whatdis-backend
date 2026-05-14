"""add daily slot unique constraint

Revision ID: 95264a11ee35
Revises: b6e4c2d8f901
Create Date: 2026-05-14 11:45:39.463841

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95264a11ee35'
down_revision = 'b6e4c2d8f901'
branch_labels = None
depends_on = None


def upgrade():
    if not _daily_slot_constraint_exists():
        with op.batch_alter_table('daily_challenges', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_daily_slot', ['available_on', 'difficulty'])


def downgrade():
    if _daily_slot_constraint_exists():
        with op.batch_alter_table('daily_challenges', schema=None) as batch_op:
            batch_op.drop_constraint('uq_daily_slot', type_='unique')


def _daily_slot_constraint_exists() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints('daily_challenges')
    if any(c.get('name') == 'uq_daily_slot' for c in unique_constraints):
        return True

    indexes = inspector.get_indexes('daily_challenges')
    return any(
        ix.get('name') == 'uq_daily_slot' and ix.get('unique')
        for ix in indexes
    )
