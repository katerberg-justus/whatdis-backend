from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.mysql import CHAR
from api import db
from api.common.base_model import BaseModel


class UserAchievement(BaseModel):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    user_id        = db.Column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = db.Column(CHAR(36), ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_at      = db.Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), server_default=db.func.now())

    user        = db.relationship("User", back_populates="achievements")
    achievement = db.relationship("Achievement")
