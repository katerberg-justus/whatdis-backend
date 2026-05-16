from sqlalchemy import String, Integer, ForeignKey, Index
from sqlalchemy.dialects.mysql import CHAR

from api import db
from api.common.base_model import BaseModel


class UserEnergyPurchase(BaseModel):
    __tablename__ = "user_energy_purchases"
    __table_args__ = (
        Index("ix_user_energy_purchases_user_created", "user_id", "created_at"),
    )

    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_checkout_session_id = db.Column(String(255), nullable=False, unique=True, index=True)
    stripe_customer_id = db.Column(String(255), nullable=True, index=True)
    stripe_payment_intent_id = db.Column(String(255), nullable=True, index=True)
    booster_id = db.Column(String(50), nullable=False)
    currency = db.Column(String(3), nullable=False)
    energy_boost = db.Column(Integer, nullable=False)

    user = db.relationship("User", back_populates="energy_purchases")
