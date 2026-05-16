from sqlalchemy import Text, Integer, ForeignKey, Index
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class BattleGuess(BaseModel):
    __tablename__ = "battle_guesses"
    __table_args__ = (
        Index("ix_battle_guesses_battle_turn", "battle_id", "turn_number"),
        Index("ix_battle_guesses_user_created", "user_id", "created_at"),
    )

    battle_id = db.Column(
        CHAR(36), ForeignKey("battles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    content = db.Column(Text, nullable=False)
    # 0=no, 1=yes, 2=indecisive, 3=refusal, 4=win, 5=possible, 6=possibly_not
    response_code = db.Column(TINYINT(unsigned=True), nullable=False)
    turn_number = db.Column(Integer, nullable=False)
    raw_response = db.Column(Text, nullable=True)

    battle = db.relationship("Battle", back_populates="guesses")
    user = db.relationship("User")
