from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from api import db
from api.common.base_model import BaseModel

PENDING = 0
ACCEPTED = 1


class Friendship(BaseModel):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )

    requester_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    addressee_id = db.Column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 0 = pending, 1 = accepted
    status = db.Column(TINYINT(unsigned=True), nullable=False, default=PENDING)

    requester = db.relationship("User", foreign_keys=[requester_id], back_populates="sent_requests")
    addressee = db.relationship("User", foreign_keys=[addressee_id], back_populates="received_requests")
