from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel

PENDING  = 0  # waiting for opponent to accept
ACTIVE   = 1  # both players in, guessing in progress
FINISHED = 2  # a player submitted a winning guess


class Battle(BaseModel):
    __tablename__ = "battles"
    __table_args__ = (
        Index("ix_battles_player_pair_status", "player1_id", "player2_id", "status"),
        Index("ix_battles_challenge_status", "challenge_id", "status"),
        Index("ix_battles_winner", "winner_id"),
        Index("ix_battles_player1_updated_created", "player1_id", "updated_at", "created_at"),
        Index("ix_battles_player2_updated_created", "player2_id", "updated_at", "created_at"),
        Index("ix_battles_player1_status_updated_created", "player1_id", "status", "updated_at", "created_at"),
        Index("ix_battles_player2_status_updated_created", "player2_id", "status", "updated_at", "created_at"),
    )

    challenge_id = db.Column(CHAR(36), nullable=False, index=True)

    player1_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    player2_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    current_turn_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    winner_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 0 = pending, 1 = active, 2 = finished
    status = db.Column(TINYINT(unsigned=True), nullable=False, default=PENDING)

    player1 = db.relationship("User", foreign_keys=[player1_id])
    player2 = db.relationship("User", foreign_keys=[player2_id])
    guesses = db.relationship(
        "BattleGuess", back_populates="battle",
        lazy="dynamic", cascade="all, delete-orphan",
        order_by="BattleGuess.turn_number",
    )
