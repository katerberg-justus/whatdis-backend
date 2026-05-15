from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Date, Boolean
from werkzeug.security import generate_password_hash, check_password_hash
from api import db
from api.common.base_model import BaseModel
from api.common.subscription_plans import DEFAULT_CURRENCY


class User(BaseModel):
    __tablename__ = "users"

    name = db.Column(String(120), nullable=False, unique=True, index=True)
    email = db.Column(String(255), nullable=True, unique=True, index=True)
    password_hash = db.Column(String(255), nullable=True)
    is_guest = db.Column(Boolean, nullable=False, default=True)
    currency = db.Column(String(3), nullable=False, default=DEFAULT_CURRENCY, server_default=DEFAULT_CURRENCY)
    language = db.Column(String(8), nullable=True)
    subscription_expires_at  = db.Column(DateTime, nullable=True)
    # Subscriber carry-over energy — null for non-subscribers
    energy_balance           = db.Column(Integer, nullable=True)
    energy_replenished_date  = db.Column(Date, nullable=True)
    # Consecutive-day streak tracking
    current_streak           = db.Column(Integer, nullable=False, default=0, server_default="0")
    streak_updated_date      = db.Column(Date, nullable=True)

    games = db.relationship("Game", back_populates="user", lazy="dynamic")
    guesses = db.relationship("Guess", back_populates="user", lazy="dynamic")
    sent_requests = db.relationship(
        "Friendship", foreign_keys="Friendship.requester_id",
        back_populates="requester", lazy="dynamic", cascade="all, delete-orphan",
    )
    received_requests = db.relationship(
        "Friendship", foreign_keys="Friendship.addressee_id",
        back_populates="addressee", lazy="dynamic", cascade="all, delete-orphan",
    )
    pack_accesses = db.relationship(
        "UserPackAccess", back_populates="user",
        lazy="dynamic", cascade="all, delete-orphan",
    )
    subscriptions = db.relationship(
        "UserSubscription", back_populates="user",
        lazy="dynamic", cascade="all, delete-orphan",
    )
    achievements = db.relationship(
        "UserAchievement", back_populates="user",
        lazy="dynamic", cascade="all, delete-orphan",
    )

    @property
    def is_subscribed(self) -> bool:
        return (
            self.subscription_expires_at is not None
            and self.subscription_expires_at > datetime.utcnow()
        )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
