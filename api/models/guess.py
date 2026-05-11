from sqlalchemy import Text, ForeignKey
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class Guess(BaseModel):
    __tablename__ = "guesses"

    game_id = db.Column(
        CHAR(36),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = db.Column(Text, nullable=False)
    # 0=no, 1=yes, 2=indecisive, 3=refusal, 4=win, 5=possible  (see api.common.response_codes)
    response_code = db.Column(TINYINT(unsigned=True), nullable=False)

    game = db.relationship("Game", back_populates="guesses")
    user = db.relationship("User", back_populates="guesses")
