from sqlalchemy import String, Text, Boolean, ForeignKey, Index
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class PushSubscription(BaseModel):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        Index("ix_push_subscriptions_user_active", "user_id", "is_active"),
    )

    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint = db.Column(Text, nullable=False)
    endpoint_hash = db.Column(String(64), nullable=False, unique=True, index=True)
    p256dh = db.Column(Text, nullable=False)
    auth = db.Column(Text, nullable=False)
    content_encoding = db.Column(String(32), nullable=False, default="aes128gcm", server_default="aes128gcm")
    user_agent = db.Column(Text, nullable=True)
    is_active = db.Column(Boolean, nullable=False, default=True, server_default="1")

    user = db.relationship("User", back_populates="push_subscriptions")
