from sqlalchemy import Text, ForeignKey, Index
from sqlalchemy.dialects.mysql import CHAR, TINYINT, VARCHAR
from api import db
from api.common.base_model import BaseModel

KIND_GUESS = "guess"
KIND_HINT = "hint"


class Guess(BaseModel):
    __tablename__ = "guesses"
    __table_args__ = (
        Index("ix_guesses_game_kind_created", "game_id", "kind", "created_at"),
        Index("ix_guesses_user_created_kind", "user_id", "created_at", "kind"),
    )

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
    # Nullable: hints have no response_code.
    response_code = db.Column(TINYINT(unsigned=True), nullable=True)
    kind = db.Column(VARCHAR(16), nullable=False, server_default=KIND_GUESS, default=KIND_GUESS)
    raw_response = db.Column(Text, nullable=True)

    game = db.relationship("Game", back_populates="guesses")
    user = db.relationship("User", back_populates="guesses")
