from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class ChallengeRating(BaseModel):
    __tablename__ = "challenge_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_challenge_rating_user_challenge"),
        Index("ix_challenge_ratings_challenge_liked", "challenge_id", "liked"),
    )

    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_id = db.Column(
        CHAR(36),
        ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    liked = db.Column(Boolean, nullable=False)

    user = db.relationship("User", back_populates="challenge_ratings")
    challenge = db.relationship("Challenge", back_populates="ratings")
