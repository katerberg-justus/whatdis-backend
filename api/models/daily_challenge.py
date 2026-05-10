from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class DailyChallenge(BaseModel):
    __tablename__ = "daily_challenges"
    __table_args__ = (
        # One slot per (date, type, difficulty) — enforces the 8-slot structure
        UniqueConstraint("available_on", "challenge_type", "difficulty", name="uq_daily_slot"),
    )

    challenge_id = db.Column(
        CHAR(36), ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    available_on = db.Column(Date, nullable=False, index=True)
    # Denormalized from Challenge for the unique constraint and fast daily queries
    challenge_type = db.Column(TINYINT(unsigned=True), nullable=False)
    difficulty = db.Column(TINYINT(unsigned=True), nullable=False)

    challenge = db.relationship("Challenge", back_populates="daily_slots")
