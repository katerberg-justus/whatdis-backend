from sqlalchemy import Boolean, String, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class UserSubscription(BaseModel):
    __tablename__ = "user_subscriptions"

    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_subscription_id = db.Column(String(255), nullable=True, unique=True, index=True)
    stripe_customer_id = db.Column(String(255), nullable=False, index=True)
    stripe_status = db.Column(String(50), nullable=True)
    # pro_weekly | pro_monthly | pro_yearly | max_weekly | max_monthly | max_yearly
    plan_id = db.Column(String(50), nullable=False)
    # active | cancelled | past_due | archived
    status = db.Column(String(20), nullable=False, default="active")
    cancel_at_period_end = db.Column(Boolean, nullable=False, default=False)
    current_period_start = db.Column(DateTime, nullable=False)
    current_period_end = db.Column(DateTime, nullable=False)
    cancelled_at = db.Column(DateTime, nullable=True)
    archived_at = db.Column(DateTime, nullable=True)
    ended_at = db.Column(DateTime, nullable=True)
    last_payment_failed_at = db.Column(DateTime, nullable=True)
    last_payment_succeeded_at = db.Column(DateTime, nullable=True)

    user = db.relationship("User", back_populates="subscriptions")
