from datetime import datetime, timezone, timedelta, date, time
from zoneinfo import ZoneInfo
from sqlalchemy import func, case
from api import db, cache
from api.common.limits import (
    ENERGY_DAILY_ANONYMOUS,
    ENERGY_DAILY_GUEST,
    ENERGY_DAILY_USER,
    ENERGY_DAILY_SUBSCRIBER,
    ENERGY_MAX_SUBSCRIBER,
)

HINT_ENERGY_COST = 5
AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")


def _today_in_amsterdam() -> date:
    return datetime.now(AMSTERDAM_TZ).date()
_ENERGY_COUNTER_SCRIPT = """
local current = redis.call("GET", KEYS[1])
if not current then
  current = ARGV[1]
  redis.call("SET", KEYS[1], current, "EX", ARGV[3])
end
current = tonumber(current)
if current == nil then
  return {-2, -1}
end
local cost = tonumber(ARGV[2])
if current < cost then
  return {0, current}
end
current = current - cost
redis.call("SET", KEYS[1], current, "EX", ARGV[3])
return {1, current}
"""


def _seconds_until_midnight() -> int:
    now = datetime.now(AMSTERDAM_TZ)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def _anon_key(ip: str) -> str:
    return f"energy:anon:{ip}"


def _energy_boost(user) -> int:
    try:
        return max(0, int(getattr(user, "energy_boost", 0) or 0))
    except (TypeError, ValueError):
        return 0


def get_energy_boost(user) -> int:
    return _energy_boost(user)


def _user_key(user) -> str:
    return f"energy:user:{user.id}"


def _daily_user_energy(user) -> int:
    return ENERGY_DAILY_GUEST if user.is_guest else ENERGY_DAILY_USER


def _max_subscriber_energy() -> int:
    return ENERGY_MAX_SUBSCRIBER


def _spend_boost(user, cost: int) -> int:
    """Consume up to `cost` from the user's boost pool. Returns leftover cost."""
    boost = _energy_boost(user)
    used = min(boost, cost)
    if used > 0:
        user.energy_boost = boost - used
    return cost - used


def _count_todays_guesses(user_id: str) -> int:
    """Energy used today (weighted: hint=5, guess=1)."""
    from api.models.guess import Guess, KIND_HINT
    from api.models.battle_guess import BattleGuess
    today_start = datetime.combine(_today_in_amsterdam(), time.min, tzinfo=AMSTERDAM_TZ)
    tomorrow_start = today_start + timedelta(days=1)
    guess_weight = case((Guess.kind == KIND_HINT, HINT_ENERGY_COST), else_=1)
    solo = db.session.execute(
        db.select(func.coalesce(func.sum(guess_weight), 0)).where(
            Guess.user_id == user_id,
            Guess.created_at >= today_start,
            Guess.created_at < tomorrow_start,
        )
    ).scalar_one()
    battle = db.session.execute(
        db.select(func.count()).select_from(BattleGuess).where(
            BattleGuess.user_id == user_id,
            BattleGuess.created_at >= today_start,
            BattleGuess.created_at < tomorrow_start,
        )
    ).scalar_one()
    return int(solo) + int(battle)


def _cached_user_energy(user) -> int | None:
    """Return cached remaining energy for a non-subscriber, or None on cache miss."""
    raw = _raw_get_int(_user_key(user))
    if raw is not None:
        return raw
    return cache.get(_user_key(user))


def _set_user_energy_cache(user, remaining: int) -> None:
    if not _raw_set_int(_user_key(user), remaining, _seconds_until_midnight()):
        cache.set(_user_key(user), remaining, timeout=_seconds_until_midnight())


def _redis_backend():
    return getattr(cache, "cache", None)


def _redis_client():
    backend = _redis_backend()
    return getattr(backend, "_write_client", None)


def _redis_key(key: str) -> str:
    backend = _redis_backend()
    if backend is None:
        return key
    prefix = backend._get_prefix() if hasattr(backend, "_get_prefix") else getattr(backend, "key_prefix", "")
    return f"{prefix}{key}"


def _raw_get_int(key: str) -> int | None:
    client = _redis_client()
    if client is None:
        return None
    value = client.get(_redis_key(key))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _raw_set_int(key: str, value: int, timeout: int) -> bool:
    client = _redis_client()
    if client is None:
        return False
    client.setex(_redis_key(key), timeout, int(value))
    return True


def _consume_cached_counter(key: str, initial: int, cost: int, timeout: int) -> tuple[bool, int] | None:
    client = _redis_client()
    if client is None:
        return None
    result = client.eval(_ENERGY_COUNTER_SCRIPT, 1, _redis_key(key), int(initial), int(cost), int(timeout))
    allowed, remaining = int(result[0]), int(result[1])
    if allowed == -2:
        cache.delete(key)
        result = client.eval(_ENERGY_COUNTER_SCRIPT, 1, _redis_key(key), int(initial), int(cost), int(timeout))
        allowed, remaining = int(result[0]), int(result[1])
    if allowed == -2:
        return None
    return allowed == 1, remaining


# ── Public API ────────────────────────────────────────────────────────────────

def get_energy(user, ip: str | None = None, is_subscribed: bool | None = None) -> int:
    """Return current energy without consuming it."""
    if user is None:
        key = _anon_key(ip)
        remaining = _raw_get_int(key)
        if remaining is None:
            remaining = cache.get(key)
        return ENERGY_DAILY_ANONYMOUS if remaining is None else remaining
    subscribed = is_subscribed if is_subscribed is not None else user.is_subscribed
    boost = _energy_boost(user)
    if subscribed:
        today = _today_in_amsterdam()
        if user.energy_replenished_date != today:
            current = user.energy_balance or 0
            return min(current + ENERGY_DAILY_SUBSCRIBER, _max_subscriber_energy()) + boost
        return (user.energy_balance or 0) + boost
    cached = _cached_user_energy(user)
    if cached is None:
        daily = _daily_user_energy(user)
        cached = max(0, daily - _count_todays_guesses(user.id))
        _set_user_energy_cache(user, cached)
    return cached + boost


def award_claim_bonus(user) -> int:
    """Award the guest-to-user energy bonus and return the new remaining energy."""
    cached = _cached_user_energy(user)
    if cached is None:
        cached = max(0, _daily_user_energy(user) - _count_todays_guesses(user.id))
    remaining = min(ENERGY_DAILY_USER, cached + ENERGY_DAILY_GUEST)
    _set_user_energy_cache(user, remaining)
    return remaining + _energy_boost(user)


def consume_energy(user, ip: str | None = None, is_subscribed: bool | None = None, cost: int = 1) -> tuple[bool, int]:
    """
    Attempt to consume `cost` energy.
    Returns (allowed, energy_remaining_after_consumption).
    Must be called before the guess is committed.
    """
    if cost < 1:
        raise ValueError("cost must be >= 1")
    if user is None:
        return _consume_anon(ip, cost)
    subscribed = is_subscribed if is_subscribed is not None else user.is_subscribed
    if subscribed:
        return _consume_subscriber(user, cost)
    return _consume_user(user, cost)


# ── Per-tier implementations ──────────────────────────────────────────────────

def _consume_anon(ip: str, cost: int) -> tuple[bool, int]:
    key = _anon_key(ip)
    timeout = _seconds_until_midnight()
    consumed = _consume_cached_counter(key, ENERGY_DAILY_ANONYMOUS, cost, timeout)
    if consumed is not None:
        return consumed

    remaining = cache.get(key)
    if remaining is None:
        remaining = ENERGY_DAILY_ANONYMOUS
    if remaining < cost:
        return False, remaining
    remaining -= cost
    cache.set(key, remaining, timeout=timeout)
    return True, remaining


def _consume_user(user, cost: int) -> tuple[bool, int]:
    cached = _cached_user_energy(user)
    if cached is not None:
        daily_remaining = cached
    else:
        daily = _daily_user_energy(user)
        daily_remaining = max(0, daily - _count_todays_guesses(user.id))

    boost = _energy_boost(user)
    if boost + daily_remaining < cost:
        return False, boost + daily_remaining

    remaining_cost = _spend_boost(user, cost)
    if remaining_cost == 0:
        return True, _energy_boost(user) + daily_remaining

    timeout = _seconds_until_midnight()
    consumed = _consume_cached_counter(_user_key(user), daily_remaining, remaining_cost, timeout)
    if consumed is not None:
        allowed, new_daily = consumed
        return allowed, _energy_boost(user) + new_daily
    if not _raw_set_int(_user_key(user), daily_remaining - remaining_cost, timeout):
        cache.set(_user_key(user), daily_remaining - remaining_cost, timeout=timeout)
    return True, _energy_boost(user) + (daily_remaining - remaining_cost)


def _consume_subscriber(user, cost: int) -> tuple[bool, int]:
    _maybe_replenish(user)
    boost = _energy_boost(user)
    balance = user.energy_balance or 0
    if boost + balance < cost:
        return False, boost + balance
    remaining_cost = _spend_boost(user, cost)
    user.energy_balance = balance - remaining_cost
    # caller commits the session together with the guess
    return True, _energy_boost(user) + user.energy_balance


def _maybe_replenish(user) -> bool:
    today = _today_in_amsterdam()
    if user.energy_replenished_date == today:
        return False
    current = user.energy_balance or 0
    user.energy_balance = min(current + ENERGY_DAILY_SUBSCRIBER, _max_subscriber_energy())
    user.energy_replenished_date = today
    return True
