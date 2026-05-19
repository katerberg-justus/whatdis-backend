from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class UserIdentity(BaseModel):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_user_identities_provider_subject"),
        Index("ix_user_identities_user_id_provider", "user_id", "provider"),
    )

    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = db.Column(String(32), nullable=False)
    subject = db.Column(String(255), nullable=False)
    email = db.Column(String(255), nullable=True)
    email_verified = db.Column(Boolean, nullable=False, default=False, server_default="0")

    user = db.relationship("User", back_populates="identities")
