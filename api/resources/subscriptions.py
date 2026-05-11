import os
import json
from datetime import datetime, timezone
from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from api import db, limiter
from api.models.user import User
from api.models.user_subscription import UserSubscription
from api.common.subscription_plans import (
    PLANS, stripe_price_id, plan_info,
    STATUS_ACTIVE, STATUS_CANCELLED, STATUS_PAST_DUE, STATUS_ARCHIVED,
)


def _active_subscription(user_id: str) -> UserSubscription | None:
    return db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.status.in_([STATUS_ACTIVE, STATUS_CANCELLED, STATUS_PAST_DUE]),
        )
    ).scalar_one_or_none()


def _serialize(sub: UserSubscription) -> dict:
    info = plan_info(sub.plan_id) or {}
    return {
        "id": sub.id,
        "plan_id": sub.plan_id,
        "tier": info.get("tier"),
        "period": info.get("period"),
        "status": sub.status,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


# ── Available plans ───────────────────────────────────────────────────────────

class SubscriptionPlanListResource(Resource):
    decorators = [limiter.limit("60 per minute")]

    def get(self):
        return [
            {
                "plan_id": plan_id,
                "tier": meta["tier"],
                "period": meta["period"],
                "stripe_price_id": stripe_price_id(plan_id),
            }
            for plan_id, meta in PLANS.items()
        ], 200


# ── Checkout ──────────────────────────────────────────────────────────────────

class CheckoutSessionResource(Resource):
    decorators = [jwt_required(), limiter.limit("10 per minute")]

    def post(self):
        uid = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        plan_id = data.get("plan_id")

        if plan_id not in PLANS:
            return {"error": f"Invalid plan_id. Choose from: {', '.join(PLANS)}"}, 400

        price_id = stripe_price_id(plan_id)
        if not price_id:
            return {"error": f"Stripe price not configured for {plan_id}"}, 500

        success_url = data.get("success_url") or os.environ.get("STRIPE_SUCCESS_URL")
        cancel_url = data.get("cancel_url") or os.environ.get("STRIPE_CANCEL_URL")
        if not success_url or not cancel_url:
            return {"error": "success_url and cancel_url are required"}, 400

        user = db.session.get(User, uid)
        if user is None:
            return {"error": "User not found"}, 404

        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

        # reuse existing Stripe customer if the user has one
        existing_sub = db.session.execute(
            db.select(UserSubscription).where(UserSubscription.user_id == uid)
            .order_by(UserSubscription.created_at.desc())
        ).scalar_one_or_none()
        customer_id = existing_sub.stripe_customer_id if existing_sub else None

        try:
            params = {
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"user_id": uid},
                "subscription_data": {"metadata": {"user_id": uid}},
            }
            if customer_id:
                params["customer"] = customer_id
            else:
                params["customer_email"] = user.email

            session = stripe.checkout.Session.create(**params)
        except stripe.StripeError as e:
            return {"error": str(e)}, 502

        return {"checkout_url": session.url}, 200


# ── Current user's subscription ───────────────────────────────────────────────

class MeSubscriptionResource(Resource):
    decorators = [jwt_required(), limiter.limit("30 per minute")]

    def get(self):
        sub = _active_subscription(get_jwt_identity())
        if sub is None:
            return {"subscription": None}, 200
        return _serialize(sub), 200

    def delete(self):
        uid = get_jwt_identity()
        sub = _active_subscription(uid)
        if sub is None:
            return {"error": "No active subscription"}, 404
        if sub.status == STATUS_CANCELLED:
            return {"error": "Subscription already cancelled"}, 409

        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        try:
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.StripeError as e:
            return {"error": str(e)}, 502

        sub.status = STATUS_CANCELLED
        sub.cancelled_at = datetime.now(timezone.utc)
        db.session.commit()
        return _serialize(sub), 200


# ── Stripe webhook ────────────────────────────────────────────────────────────

class StripeWebhookResource(Resource):

    def post(self):
        payload = request.get_data()
        sig = request.headers.get("Stripe-Signature", "")
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        try:
            stripe.Webhook.construct_event(payload, sig, secret)
        except (stripe.SignatureVerificationError, ValueError):
            return {"error": "Invalid signature"}, 400

        event_dict = json.loads(payload)
        data = event_dict["data"]["object"]
        etype = event_dict["type"]

        if etype == "customer.subscription.created":
            _handle_subscription_upsert(data)
        elif etype == "customer.subscription.updated":
            _handle_subscription_upsert(data)
        elif etype == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif etype in ("invoice.payment_failed", "invoice.payment_action_required"):
            _handle_payment_failed(data)

        return {}, 200


# ── Webhook handlers ──────────────────────────────────────────────────────────

def _handle_subscription_upsert(data: dict):
    stripe_sub_id = data["id"]
    stripe_customer_id = data["customer"]
    stripe_status = data["status"]
    period_start_ts = data.get("current_period_start")
    period_end_ts = data.get("current_period_end")
    period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc) if period_start_ts else None
    period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc) if period_end_ts else None

    price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
    plan_id = _plan_id_from_price(price_id)

    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()

    local_status = _map_stripe_status(stripe_status, sub)

    if sub is None:
        uid = (data.get("metadata") or {}).get("user_id")
        user = db.session.get(User, uid) if uid else _user_from_customer(stripe_customer_id)
        if user is None:
            return
        sub = UserSubscription(
            user_id=user.id,
            stripe_subscription_id=stripe_sub_id,
            stripe_customer_id=stripe_customer_id,
            plan_id=plan_id or "",
            status=local_status,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db.session.add(sub)
    else:
        if plan_id:
            sub.plan_id = plan_id
        sub.status = local_status
        sub.current_period_start = period_start
        sub.current_period_end = period_end

    if period_end:
        _sync_user_expiry(sub.user_id, period_end if local_status == STATUS_ACTIVE else None)
    db.session.commit()


def _handle_subscription_deleted(data: dict):
    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == data["id"]
        )
    ).scalar_one_or_none()

    if sub is None:
        return

    sub.status = STATUS_ARCHIVED
    sub.archived_at = datetime.now(timezone.utc)
    _sync_user_expiry(sub.user_id, None)
    db.session.commit()


def _handle_payment_failed(data: dict):
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return

    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()

    if sub:
        sub.status = STATUS_PAST_DUE
        db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_stripe_status(stripe_status: str, existing: UserSubscription | None) -> str:
    if stripe_status in ("active", "trialing"):
        # preserve local cancelled flag if user already requested cancellation
        if existing and existing.status == STATUS_CANCELLED:
            return STATUS_CANCELLED
        return STATUS_ACTIVE
    if stripe_status == "past_due":
        return STATUS_PAST_DUE
    if stripe_status in ("canceled", "unpaid", "incomplete_expired"):
        return STATUS_ARCHIVED
    return STATUS_ACTIVE


def _plan_id_from_price(price_id: str | None) -> str | None:
    if not price_id:
        return None
    for plan_id, meta in PLANS.items():
        if os.environ.get(meta["price_env"]) == price_id:
            return plan_id
    return None


def _user_from_customer(stripe_customer_id: str) -> User | None:
    existing_sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_customer_id == stripe_customer_id
        )
    ).scalar_one_or_none()
    if existing_sub:
        return db.session.get(User, existing_sub.user_id)
    return None


def _sync_user_expiry(user_id: str, expiry: datetime | None):
    user = db.session.get(User, user_id)
    if user:
        user.subscription_expires_at = expiry
