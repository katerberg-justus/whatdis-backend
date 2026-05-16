from sqlalchemy import String, ForeignKey, DateTime, Index
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class Game(BaseModel):
    __tablename__ = "games"
    __table_args__ = (
        Index("ix_games_user_challenge", "user_id", "challenge_id"),
        Index("ix_games_user_completed_challenge", "user_id", "completed_at", "challenge_id"),
    )

    challenge_id = db.Column(CHAR(36), nullable=False, index=True)
    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_at = db.Column(DateTime, nullable=True)

    user = db.relationship("User", back_populates="games")
    guesses = db.relationship(
        "Guess", back_populates="game", lazy="dynamic", cascade="all, delete-orphan"
    )
