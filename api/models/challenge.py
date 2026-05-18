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
    subject_hint = db.Column(String(160), nullable=True)
    # 0=easy, 1=medium, 2=hard, 3=impossible
    difficulty = db.Column(TINYINT(unsigned=True), nullable=False, index=True)
    is_active = db.Column(Boolean, nullable=False, default=True, server_default="1")
    sticker = db.Column(Text, nullable=True)
    position = db.Column(Integer, nullable=False, default=0, server_default="0")
    created_by_user_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    share_token = db.Column(String(16), nullable=True, unique=True, index=True)

    pack = db.relationship("ChallengePack", back_populates="challenges")
    daily_slots = db.relationship(
        "DailyChallenge", back_populates="challenge", lazy="dynamic",
    )
    accesses = db.relationship(
        "UserChallengeAccess", back_populates="challenge",
        lazy="dynamic", cascade="all, delete-orphan",
    )
