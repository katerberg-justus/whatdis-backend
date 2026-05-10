from sqlalchemy import Text, Integer, ForeignKey
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class BattleGuess(BaseModel):
    __tablename__ = "battle_guesses"

    battle_id = db.Column(
        CHAR(36), ForeignKey("battles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    content = db.Column(Text, nullable=False)
    # 0=no, 1=yes, 2=indecisive, 3=refusal, 4=win
    response_code = db.Column(TINYINT(unsigned=True), nullable=False)
    turn_number = db.Column(Integer, nullable=False)

    battle = db.relationship("Battle", back_populates="guesses")
    user = db.relationship("User")
