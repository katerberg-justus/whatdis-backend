"""drop icon from challenges

Revision ID: 4a7d2c91b5e8
Revises: 187928bf31e6
Create Date: 2026-05-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a7d2c91b5e8'
down_revision = '187928bf31e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.drop_column('icon')


def downgrade():
    with op.batch_alter_table('challenges', schema=None) as batch_op:
        batch_op.add_column(sa.Column('icon', sa.Text(), nullable=True))
