from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class UserPackAccess(BaseModel):
    __tablename__ = "user_pack_accesses"
    __table_args__ = (
        UniqueConstraint("user_id", "pack_id", name="uq_user_pack"),
    )

    user_id = db.Column(
        CHAR(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    pack_id = db.Column(
        CHAR(36), ForeignKey("challenge_packs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    user = db.relationship("User", back_populates="pack_accesses")
    pack = db.relationship("ChallengePack", back_populates="user_accesses")
