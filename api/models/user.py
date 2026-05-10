from sqlalchemy import String
from werkzeug.security import generate_password_hash, check_password_hash
from api import db
from api.common.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    name = db.Column(String(120), nullable=False)
    email = db.Column(String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(String(255), nullable=False)

    games = db.relationship("Game", back_populates="user", lazy="dynamic")
    guesses = db.relationship("Guess", back_populates="user", lazy="dynamic")
    sent_requests = db.relationship(
        "Friendship", foreign_keys="Friendship.requester_id",
        back_populates="requester", lazy="dynamic", cascade="all, delete-orphan",
    )
    received_requests = db.relationship(
        "Friendship", foreign_keys="Friendship.addressee_id",
        back_populates="addressee", lazy="dynamic", cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
