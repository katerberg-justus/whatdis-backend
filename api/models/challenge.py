from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, Index
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class Challenge(BaseModel):
    __tablename__ = "challenges"
    __table_args__ = (
        Index("ix_challenges_pack_position", "pack_id", "position"),
    )

    pack_id = db.Column(
        CHAR(36), ForeignKey("challenge_packs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subject = db.Column(String(255), nullable=False)
    # 0=easy, 1=medium, 2=hard, 3=impossible
    difficulty = db.Column(TINYINT(unsigned=True), nullable=False, index=True)
    is_active = db.Column(Boolean, nullable=False, default=True, server_default="1")
    icon = db.Column(Text, nullable=True)
    position = db.Column(Integer, nullable=False, default=0, server_default="0")

    pack = db.relationship("ChallengePack", back_populates="challenges")
    daily_slots = db.relationship(
        "DailyChallenge", back_populates="challenge", lazy="dynamic",
    )
