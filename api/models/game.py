from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class Game(BaseModel):
    __tablename__ = "games"

    challenge_id = db.Column(CHAR(36), nullable=False, index=True)
    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = db.relationship("User", back_populates="games")
    guesses = db.relationship(
        "Guess", back_populates="game", lazy="dynamic", cascade="all, delete-orphan"
    )
