import os

from api.common.subscription_plans import DEFAULT_CURRENCY, normalize_currency

NRG_1K = "nrg_booster_1k"
NRG_5K = "nrg_booster_5k"
NRG_10K = "nrg_booster_10k"

BOOSTERS = {
    NRG_1K: {
        "name": "1K NRG Booster",
        "energy_boost": 1000,
        "price_env": "STRIPE_PRICE_NRG_BOOSTER_1K",
    },
    NRG_5K: {
        "name": "5K NRG Booster",
        "energy_boost": 5000,
        "price_env": "STRIPE_PRICE_NRG_BOOSTER_5K",
    },
    NRG_10K: {
        "name": "10K NRG Booster",
        "energy_boost": 10000,
        "price_env": "STRIPE_PRICE_NRG_BOOSTER_10K",
    },
}

VALID_BOOSTER_IDS = set(BOOSTERS.keys())


def booster_info(booster_id: str) -> dict | None:
    return BOOSTERS.get(booster_id)


def stripe_price_id_for_booster(booster_id: str) -> str | None:
    return stripe_price_id_for_booster_currency(booster_id, DEFAULT_CURRENCY)


def stripe_price_id_for_booster_currency(booster_id: str, currency: str) -> str | None:
    booster = BOOSTERS.get(booster_id)
    normalized = normalize_currency(currency)
    if not booster or not normalized:
        return None

    currency_env = f"{booster['price_env']}_{normalized}"
    price_id = os.environ.get(currency_env)
    if price_id:
        return price_id

    return os.environ.get(booster["price_env"])
