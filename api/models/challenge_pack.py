from sqlalchemy import String, Text, Boolean
from sqlalchemy.dialects.mysql import TINYINT
from api import db
from api.common.base_model import BaseModel


class ChallengePack(BaseModel):
    __tablename__ = "challenge_packs"

    name = db.Column(String(120), nullable=False)
    description = db.Column(Text, nullable=True)
    # 0=person, 1=object, 2=mixed
    challenge_type = db.Column(TINYINT(unsigned=True), nullable=False)
    # 0=easy, 1=medium, 2=hard, 3=impossible, 4=mixed
    difficulty = db.Column(TINYINT(unsigned=True), nullable=False)
    is_active = db.Column(Boolean, nullable=False, default=True)

    challenges = db.relationship(
        "Challenge", back_populates="pack",
        lazy="dynamic", cascade="all, delete-orphan",
    )
    user_accesses = db.relationship(
        "UserPackAccess", back_populates="pack",
        lazy="dynamic", cascade="all, delete-orphan",
    )
