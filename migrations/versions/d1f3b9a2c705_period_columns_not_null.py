"""make current_period_start/end NOT NULL on user_subscriptions; remove dirty rows

Revision ID: d1f3b9a2c705
Revises: c3f1a2b4d8e9
Create Date: 2026-05-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = 'd1f3b9a2c705'
down_revision = 'c3f1a2b4d8e9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Delete rows with NULL period columns — these were never properly
    #    populated by a Stripe webhook and can't be recovered.
    conn.execute(text("""
        DELETE FROM user_subscriptions
        WHERE current_period_start IS NULL
           OR current_period_end IS NULL
    """))

    # 2. Archive duplicate active subscriptions per user, keeping only the
    #    most recently created one. Duplicates arise when a second Checkout
    #    session completes before the old subscription is archived.
    conn.execute(text("""
        UPDATE user_subscriptions s
        JOIN (
            SELECT id
            FROM user_subscriptions
            WHERE status IN ('active', 'cancelled', 'past_due')
              AND id NOT IN (
                  SELECT MAX(id)
                  FROM user_subscriptions
                  WHERE status IN ('active', 'cancelled', 'past_due')
                  GROUP BY user_id
              )
        ) dupes ON s.id = dupes.id
        SET s.status = 'archived',
            s.archived_at = UTC_TIMESTAMP()
    """))

    # 3. Now safe to enforce NOT NULL.
    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('current_period_start',
            existing_type=sa.DateTime(),
            nullable=False)
        batch_op.alter_column('current_period_end',
            existing_type=sa.DateTime(),
            nullable=False)


def downgrade():
    with op.batch_alter_table('user_subscriptions', schema=None) as batch_op:
        batch_op.alter_column('current_period_start',
            existing_type=sa.DateTime(),
            nullable=True)
        batch_op.alter_column('current_period_end',
            existing_type=sa.DateTime(),
            nullable=True)
