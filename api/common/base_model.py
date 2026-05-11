from datetime import datetime, timezone
from sqlalchemy import text, DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from api import db


def utc_isoformat(dt: datetime | None) -> str | None:
    """Return an ISO-8601 Zulu string for any datetime, naive or aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
