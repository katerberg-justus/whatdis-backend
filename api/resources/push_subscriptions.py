from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from api import db, limiter
from api.models.push_subscription import PushSubscription
from api.services.push_notifications import endpoint_hash, vapid_public_key, web_push_configured


def _subscription_payload(data: dict) -> tuple[dict | None, dict | None]:
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not endpoint or not p256dh or not auth:
        return None, {"error": "endpoint, keys.p256dh, and keys.auth are required"}
    return {
        "endpoint": str(endpoint),
        "p256dh": str(p256dh),
        "auth": str(auth),
        "content_encoding": str(data.get("contentEncoding") or data.get("content_encoding") or "aes128gcm"),
    }, None


class PushVapidPublicKeyResource(Resource):
    decorators = [limiter.limit("60 per minute")]

    def get(self):
        public_key = vapid_public_key()
        return {
            "public_key": public_key,
            "configured": web_push_configured(),
        }, 200


class PushSubscriptionListResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def post(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        payload, error = _subscription_payload(data)
        if error:
            return error, 400

        hashed = endpoint_hash(payload["endpoint"])
        subscription = db.session.execute(
            db.select(PushSubscription).where(PushSubscription.endpoint_hash == hashed)
        ).scalar_one_or_none()

        if subscription is None:
            subscription = PushSubscription(user_id=uid, endpoint_hash=hashed)
            db.session.add(subscription)

        subscription.user_id = uid
        subscription.endpoint = payload["endpoint"]
        subscription.p256dh = payload["p256dh"]
        subscription.auth = payload["auth"]
        subscription.content_encoding = payload["content_encoding"]
        subscription.user_agent = request.headers.get("User-Agent")
        subscription.is_active = True
        db.session.commit()
        return {"id": subscription.id}, 201

    def delete(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        endpoint = data.get("endpoint")
        if not endpoint:
            return {"error": "endpoint required"}, 400

        subscription = db.session.execute(
            db.select(PushSubscription).where(
                PushSubscription.endpoint_hash == endpoint_hash(str(endpoint)),
                PushSubscription.user_id == uid,
            )
        ).scalar_one_or_none()
        if subscription is None:
            return {}, 204

        db.session.delete(subscription)
        db.session.commit()
        return {}, 204


class PushSubscriptionResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def delete(self, subscription_id):
        uid = get_jwt_identity()
        subscription = db.session.get(PushSubscription, subscription_id)
        if subscription is None:
            return {}, 204
        if subscription.user_id != uid:
            abort(403)
        db.session.delete(subscription)
        db.session.commit()
        return {}, 204
