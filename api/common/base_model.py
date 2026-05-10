from sqlalchemy import text, DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from api import db


class BaseModel(db.Model):
    __abstract__ = True

    id = db.Column(
        CHAR(36),
        primary_key=True,
        server_default=text("UUID_V7()"),
        nullable=False,
    )
    created_at = db.Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at = db.Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
