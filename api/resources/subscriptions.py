import os
import json
from datetime import datetime, timezone
from flask import request
from flask_restful import Resource, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
import stripe
from api import db, limiter
from api.common.base_model import utc_isoformat
from api.models.user import User
from api.models.user_subscription import UserSubscription
from api.common.subscription_plans import (
    DEFAULT_CURRENCY,
    PLANS,
    SUPPORTED_CURRENCIES,
    normalize_currency,
    stripe_price_id,
    stripe_price_id_for_currency,
    plan_info,
    STATUS_ACTIVE, STATUS_CANCELLED, STATUS_PAST_DUE, STATUS_ARCHIVED,
)


def _active_subscription(user_id: str) -> UserSubscription | None:
    return db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.status.in_([STATUS_ACTIVE, STATUS_CANCELLED, STATUS_PAST_DUE]),
        ).order_by(UserSubscription.created_at.desc())
    ).scalars().first()


def _serialize(sub: UserSubscription) -> dict:
    info = plan_info(sub.plan_id) or {}
    return {
        "id": sub.id,
        "plan_id": sub.plan_id,
        "tier": info.get("tier"),
        "period": info.get("period"),
        "status": sub.status,
        "stripe_status": sub.stripe_status,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_start": utc_isoformat(sub.current_period_start),
        "current_period_end": utc_isoformat(sub.current_period_end),
        "cancelled_at": utc_isoformat(sub.cancelled_at),
        "ended_at": utc_isoformat(sub.ended_at),
        "last_payment_failed_at": utc_isoformat(sub.last_payment_failed_at),
        "last_payment_succeeded_at": utc_isoformat(sub.last_payment_succeeded_at),
        "created_at": utc_isoformat(sub.created_at),
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

        success_url = data.get("success_url") or os.environ.get("STRIPE_SUCCESS_URL")
        cancel_url = data.get("cancel_url") or os.environ.get("STRIPE_CANCEL_URL")
        if not success_url or not cancel_url:
            return {"error": "success_url and cancel_url are required"}, 400

        user = db.session.get(User, uid)
        if user is None:
            return {"error": "User not found"}, 404

        currency = normalize_currency(data.get("currency") or user.currency or DEFAULT_CURRENCY)
        if currency is None:
            return {"error": f"Invalid currency. Choose from: {', '.join(sorted(SUPPORTED_CURRENCIES))}"}, 400

        price_id = stripe_price_id_for_currency(plan_id, currency)
        if not price_id:
            return {"error": f"Stripe price not configured for {plan_id} in {currency}"}, 500

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
                "metadata": {"user_id": uid, "currency": currency},
                "subscription_data": {"metadata": {"user_id": uid, "currency": currency}},
                "allow_promotion_codes": True,
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
        sub.cancel_at_period_end = True
        sub.cancelled_at = datetime.now(timezone.utc)
        db.session.commit()
        return _serialize(sub), 200


# ── Stripe webhook ────────────────────────────────────────────────────────────

class StripeWebhookResource(Resource):

    def post(self):
        payload = request.get_data()
        sig = request.headers.get("Stripe-Signature", "")
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        if not secret:
            print("[webhook] STRIPE_WEBHOOK_SECRET is not configured")
            return {"error": "Webhook secret not configured"}, 500

        try:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        except stripe.SignatureVerificationError as e:
            print(f"[webhook] Invalid Stripe signature: {e}")
            return {"error": "Invalid signature"}, 400
        except ValueError as e:
            print(f"[webhook] Invalid Stripe payload: {e}")
            return {"error": "Invalid signature"}, 400

        event_dict = _stripe_obj_to_dict(event)
        data = event_dict["data"]["object"]
        etype = event_dict["type"]

        if etype == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif etype in ("customer.subscription.created", "customer.subscription.updated"):
            _handle_subscription_upsert(data)
        elif etype == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif etype in ("invoice.payment_failed", "invoice.payment_action_required"):
            _handle_payment_failed(data)
        elif etype == "invoice.payment_succeeded":
            _handle_payment_succeeded(data)

        return {}, 200


# ── Webhook handlers ──────────────────────────────────────────────────────────

def _handle_checkout_completed(data: dict):
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return

    sub_data = _retrieve_subscription(stripe_sub_id)
    if not sub_data:
        return

    _handle_subscription_upsert(sub_data)


def _handle_subscription_upsert(data: dict, *, fetched: bool = False):
    stripe_sub_id = data["id"]
    stripe_customer_id = data["customer"]
    stripe_status = data["status"]
    cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    period_start_ts = data.get("current_period_start")
    period_end_ts = data.get("current_period_end")
    # Flexible billing mode subscriptions omit current_period_start/end.
    # The invoice top-level period_start/end is just when items were added;
    # the actual service window is on the first line item's period.
    if not period_start_ts or not period_end_ts:
        invoice = data.get("latest_invoice") or {}
        if isinstance(invoice, dict):
            line = ((invoice.get("lines") or {}).get("data") or [{}])[0]
            line_period = line.get("period") or {}
            period_start_ts = period_start_ts or line_period.get("start")
            period_end_ts = period_end_ts or line_period.get("end")
    if (not period_start_ts or not period_end_ts) and not fetched:
        fetched_data = _retrieve_subscription(stripe_sub_id)
        if fetched_data:
            return _handle_subscription_upsert(fetched_data, fetched=True)

    period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc) if period_start_ts else None
    period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc) if period_end_ts else None

    price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
    plan_id = _plan_id_from_price(price_id)
    if not plan_id:
        print(f"[webhook] Unknown Stripe price for subscription {stripe_sub_id}: {price_id}")
        return

    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()

    local_status = _map_stripe_status(stripe_status, sub, cancel_at_period_end)
    canceled_at = _datetime_from_timestamp(data.get("canceled_at"))
    ended_at = _datetime_from_timestamp(data.get("ended_at"))

    if sub is None:
        if not period_start or not period_end:
            print(f"[webhook] Missing period dates for subscription {stripe_sub_id}")
            return
        uid = (data.get("metadata") or {}).get("user_id")
        user = db.session.get(User, uid) if uid else _user_from_customer(stripe_customer_id)
        if user is None:
            print(f"[webhook] Could not match subscription {stripe_sub_id} to a user")
            return
        # archive any previous active subscription for this user
        db.session.execute(
            db.update(UserSubscription).where(
                UserSubscription.user_id == user.id,
                UserSubscription.stripe_subscription_id != stripe_sub_id,
                UserSubscription.status.in_([STATUS_ACTIVE, STATUS_CANCELLED, STATUS_PAST_DUE]),
            ).values(status=STATUS_ARCHIVED, archived_at=datetime.now(timezone.utc))
        )
        sub = UserSubscription(
            user_id=user.id,
            stripe_subscription_id=stripe_sub_id,
            stripe_customer_id=stripe_customer_id,
            stripe_status=stripe_status,
            plan_id=plan_id,
            status=local_status,
            cancel_at_period_end=cancel_at_period_end,
            current_period_start=period_start,
            current_period_end=period_end,
            cancelled_at=canceled_at,
            ended_at=ended_at,
        )
        db.session.add(sub)
    else:
        sub.plan_id = plan_id
        sub.stripe_status = stripe_status
        sub.status = local_status
        sub.cancel_at_period_end = cancel_at_period_end
        if canceled_at:
            sub.cancelled_at = canceled_at
        elif cancel_at_period_end and not sub.cancelled_at:
            sub.cancelled_at = datetime.now(timezone.utc)
        if ended_at:
            sub.ended_at = ended_at
        if period_start:
            sub.current_period_start = period_start
        if period_end:
            sub.current_period_end = period_end

    _sync_user_expiry(sub.user_id, period_end if local_status in (STATUS_ACTIVE, STATUS_CANCELLED) else None)
    db.session.commit()


def _handle_subscription_deleted(data: dict):
    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == data["id"]
        )
    ).scalar_one_or_none()

    if sub is None:
        return

    sub.stripe_status = data.get("status") or "canceled"
    sub.status = STATUS_ARCHIVED
    sub.cancel_at_period_end = False
    sub.ended_at = _datetime_from_timestamp(data.get("ended_at")) or datetime.now(timezone.utc)
    sub.archived_at = datetime.now(timezone.utc)
    _sync_user_expiry(sub.user_id, None)
    db.session.commit()


def _handle_payment_failed(data: dict):
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return

    sub_data = _retrieve_subscription(stripe_sub_id)
    if sub_data:
        _handle_subscription_upsert(sub_data)

    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()

    if sub:
        sub.status = STATUS_PAST_DUE
        sub.last_payment_failed_at = datetime.now(timezone.utc)
        _sync_user_expiry(sub.user_id, None)
        db.session.commit()


def _handle_payment_succeeded(data: dict):
    stripe_sub_id = data.get("subscription")
    if not stripe_sub_id:
        return

    sub_data = _retrieve_subscription(stripe_sub_id)
    if sub_data:
        _handle_subscription_upsert(sub_data)

    sub = db.session.execute(
        db.select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_sub_id
        )
    ).scalar_one_or_none()

    if sub:
        sub.last_payment_succeeded_at = datetime.now(timezone.utc)
        if sub.status in (STATUS_ACTIVE, STATUS_CANCELLED):
            sub.last_payment_failed_at = None
        db.session.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_stripe_status(
    stripe_status: str,
    existing: UserSubscription | None,
    cancel_at_period_end: bool = False,
) -> str:
    if stripe_status in ("active", "trialing"):
        if cancel_at_period_end:
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
        for currency in SUPPORTED_CURRENCIES:
            if stripe_price_id_for_currency(plan_id, currency) == price_id:
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


def _retrieve_subscription(stripe_sub_id: str) -> dict | None:
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    try:
        sub_data = stripe.Subscription.retrieve(stripe_sub_id, expand=["latest_invoice"])
    except stripe.StripeError as e:
        print(f"[webhook] Stripe retrieve error for subscription {stripe_sub_id}: {e}")
        return None
    return _stripe_obj_to_dict(sub_data)


def _stripe_obj_to_dict(value) -> dict:
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _datetime_from_timestamp(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)
