from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class UserChallengeAccess(BaseModel):
    __tablename__ = "user_challenge_accesses"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_user_challenge_access"),
    )

    user_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    challenge_id = db.Column(
        CHAR(36), ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    challenge = db.relationship("Challenge", back_populates="accesses")
