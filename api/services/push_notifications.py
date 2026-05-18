import hashlib
import json
import os
from typing import Iterable

from api import db
from api.models.push_subscription import PushSubscription

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - keeps local dev usable before deps are installed
    WebPushException = None
    webpush = None


def vapid_public_key() -> str | None:
    return os.environ.get("VAPID_PUBLIC_KEY") or None


def _vapid_private_key() -> str | None:
    return os.environ.get("VAPID_PRIVATE_KEY") or None


def _vapid_subject() -> str:
    return os.environ.get("VAPID_SUBJECT", "mailto:support@whatdis.nl")


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def web_push_configured() -> bool:
    return bool(webpush and vapid_public_key() and _vapid_private_key())


def send_to_user(user_id: str, payload: dict) -> None:
    subscriptions = db.session.execute(
        db.select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,
        )
    ).scalars().all()
    _send_many(subscriptions, payload)


def send_to_all(payload: dict) -> None:
    subscriptions = db.session.execute(
        db.select(PushSubscription).where(PushSubscription.is_active == True)
    ).scalars().all()
    _send_many(subscriptions, payload)


def _send_many(subscriptions: Iterable[PushSubscription], payload: dict) -> None:
    if not web_push_configured():
        return

    stale = []
    data = json.dumps(payload)
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=data,
                vapid_private_key=_vapid_private_key(),
                vapid_claims={"sub": _vapid_subject()},
                content_encoding=sub.content_encoding or "aes128gcm",
                ttl=60 * 60 * 24,
                timeout=10,
            )
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if WebPushException is not None and isinstance(exc, WebPushException) and status_code in (404, 410):
                stale.append(sub)

    if stale:
        for sub in stale:
            db.session.delete(sub)
        db.session.commit()
