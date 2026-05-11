"""add position to challenges

Revision ID: 8d3979b85f71
Revises: 92772838eb65
Create Date: 2026-05-11 21:20:51.084217

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d3979b85f71'
down_revision = '92772838eb65'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.create_index('ix_challenges_pack_position', ['pack_id', 'position'], unique=False)


def downgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.drop_index('ix_challenges_pack_position')
        batch_op.drop_column('position')
