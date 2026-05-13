"""add stripe subscription state fields

Revision ID: b6e4c2d8f901
Revises: 9f4b7a6c2d31
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6e4c2d8f901'
down_revision = '9f4b7a6c2d31'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('ended_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_payment_failed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_payment_succeeded_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('cancel_at_period_end', server_default=None)


def downgrade():
    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.drop_column('last_payment_succeeded_at')
        batch_op.drop_column('last_payment_failed_at')
        batch_op.drop_column('ended_at')
        batch_op.drop_column('cancel_at_period_end')
        batch_op.drop_column('stripe_status')
