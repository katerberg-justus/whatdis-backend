from sqlalchemy import String, Text, Integer, Index
from api import db
from api.common.base_model import BaseModel


class Achievement(BaseModel):
    __tablename__ = "achievements"
    __table_args__ = (
        Index("ix_achievements_category_threshold", "category", "threshold"),
    )

    name        = db.Column(String(100), nullable=False, unique=True)
    description = db.Column(Text, nullable=False)
    # guesses | wins | daily | streak | battle_played | battle_won
    category    = db.Column(String(20), nullable=False, index=True)
    threshold   = db.Column(Integer, nullable=False)
    icon        = db.Column(Text, nullable=True)
