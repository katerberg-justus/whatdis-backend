import os

PRO = "pro"

WEEKLY  = "weekly"
MONTHLY = "monthly"
YEARLY  = "yearly"

# status lifecycle: active -> cancelled (period still running) -> archived (fully ended)
STATUS_ACTIVE    = "active"
STATUS_CANCELLED = "cancelled"
STATUS_PAST_DUE  = "past_due"
STATUS_ARCHIVED  = "archived"

PLANS = {
    f"{PRO}_{WEEKLY}":  {"tier": PRO, "period": WEEKLY,  "price_env": "STRIPE_PRICE_PRO_WEEKLY"},
    f"{PRO}_{MONTHLY}": {"tier": PRO, "period": MONTHLY, "price_env": "STRIPE_PRICE_PRO_MONTHLY"},
    f"{PRO}_{YEARLY}":  {"tier": PRO, "period": YEARLY,  "price_env": "STRIPE_PRICE_PRO_YEARLY"},
}

VALID_PLAN_IDS = set(PLANS.keys())


def plan_info(plan_id: str) -> dict | None:
    return PLANS.get(plan_id)


def stripe_price_id(plan_id: str) -> str | None:
    plan = PLANS.get(plan_id)
    return os.environ.get(plan["price_env"]) if plan else None
