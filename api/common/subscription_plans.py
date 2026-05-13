import os

PRO = "pro"

WEEKLY  = "weekly"
MONTHLY = "monthly"
YEARLY  = "yearly"

DEFAULT_CURRENCY = "EUR"
SUPPORTED_CURRENCIES = {"EUR", "USD", "GBP"}

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
    return stripe_price_id_for_currency(plan_id, DEFAULT_CURRENCY)


def normalize_currency(currency: str | None) -> str | None:
    if not isinstance(currency, str):
        return None
    normalized = currency.strip().upper()
    return normalized if normalized in SUPPORTED_CURRENCIES else None


def stripe_price_id_for_currency(plan_id: str, currency: str) -> str | None:
    plan = PLANS.get(plan_id)
    normalized = normalize_currency(currency)
    if not plan or not normalized:
        return None

    currency_env = f"{plan['price_env']}_{normalized}"
    price_id = os.environ.get(currency_env)
    if price_id:
        return price_id

    if normalized == DEFAULT_CURRENCY:
        return os.environ.get(plan["price_env"])
    return None
