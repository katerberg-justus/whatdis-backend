from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel


class Challenge(BaseModel):
    __tablename__ = "challenges"

    pack_id = db.Column(
        CHAR(36), ForeignKey("challenge_packs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subject = db.Column(String(255), nullable=False)
    # 0=person, 1=object
    challenge_type = db.Column(TINYINT(unsigned=True), nullable=False)
    # 0=easy, 1=medium, 2=hard, 3=impossible
    difficulty = db.Column(TINYINT(unsigned=True), nullable=False, index=True)
    is_active = db.Column(Boolean, nullable=False, default=True)

    pack = db.relationship("ChallengePack", back_populates="challenges")
    daily_slots = db.relationship(
        "DailyChallenge", back_populates="challenge", lazy="dynamic",
    )
