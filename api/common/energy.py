from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func, cast, case, Date as SADate
from api import db, cache
from api.common.limits import (
    ENERGY_DAILY_ANONYMOUS,
    ENERGY_DAILY_GUEST,
    ENERGY_DAILY_USER,
    ENERGY_DAILY_SUBSCRIBER,
    ENERGY_MAX_SUBSCRIBER,
)

HINT_ENERGY_COST = 5


def _seconds_until_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def _anon_key(ip: str) -> str:
    return f"energy:anon:{ip}"


def _user_key(user_id: str) -> str:
    return f"energy:user:{user_id}"


def _count_todays_guesses(user_id: str) -> int:
    """Energy used today (weighted: hint=5, guess=1)."""
    from api.models.guess import Guess, KIND_HINT
    from api.models.battle_guess import BattleGuess
    today = date.today()
    guess_weight = case((Guess.kind == KIND_HINT, HINT_ENERGY_COST), else_=1)
    solo = db.session.execute(
        db.select(func.coalesce(func.sum(guess_weight), 0)).where(
            Guess.user_id == user_id,
            cast(Guess.created_at, SADate) == today,
        )
    ).scalar_one()
    battle = db.session.execute(
        db.select(func.count()).select_from(BattleGuess).where(
            BattleGuess.user_id == user_id,
            cast(BattleGuess.created_at, SADate) == today,
        )
    ).scalar_one()
    return int(solo) + int(battle)


def _cached_user_energy(user_id: str) -> int | None:
    """Return cached remaining energy for a non-subscriber, or None on cache miss."""
    return cache.get(_user_key(user_id))


def _set_user_energy_cache(user_id: str, remaining: int) -> None:
    cache.set(_user_key(user_id), remaining, timeout=_seconds_until_midnight())


# ── Public API ────────────────────────────────────────────────────────────────

def get_energy(user, ip: str | None = None, is_subscribed: bool | None = None) -> int:
    """Return current energy without consuming it."""
    if user is None:
        remaining = cache.get(_anon_key(ip))
        return ENERGY_DAILY_ANONYMOUS if remaining is None else remaining
    subscribed = is_subscribed if is_subscribed is not None else user.is_subscribed
    if subscribed:
        today = date.today()
        if user.energy_replenished_date != today:
            current = user.energy_balance or 0
            return min(current + ENERGY_DAILY_SUBSCRIBER, ENERGY_MAX_SUBSCRIBER)
        return user.energy_balance or 0
    cached = _cached_user_energy(user.id)
    if cached is not None:
        return cached
    daily = ENERGY_DAILY_GUEST if user.is_guest else ENERGY_DAILY_USER
    remaining = max(0, daily - _count_todays_guesses(user.id))
    _set_user_energy_cache(user.id, remaining)
    return remaining


def award_claim_bonus(user) -> int:
    """Award the guest-to-user energy bonus and return the new remaining energy."""
    remaining = get_energy(user, is_subscribed=False)
    remaining = min(ENERGY_DAILY_USER, remaining + ENERGY_DAILY_GUEST)
    _set_user_energy_cache(user.id, remaining)
    return remaining


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
    remaining = cache.get(key)
    if remaining is None:
        remaining = ENERGY_DAILY_ANONYMOUS
    if remaining < cost:
        return False, remaining
    remaining -= cost
    cache.set(key, remaining, timeout=_seconds_until_midnight())
    return True, remaining


def _consume_user(user, cost: int) -> tuple[bool, int]:
    cached = _cached_user_energy(user.id)
    if cached is not None:
        remaining = cached
    else:
        daily = ENERGY_DAILY_GUEST if user.is_guest else ENERGY_DAILY_USER
        remaining = max(0, daily - _count_todays_guesses(user.id))
    if remaining < cost:
        return False, remaining
    _set_user_energy_cache(user.id, remaining - cost)
    return True, remaining - cost


def _consume_subscriber(user, cost: int) -> tuple[bool, int]:
    _maybe_replenish(user)
    balance = user.energy_balance or 0
    if balance < cost:
        return False, balance
    user.energy_balance = balance - cost
    # caller commits the session together with the guess
    return True, user.energy_balance


def _maybe_replenish(user) -> bool:
    today = date.today()
    if user.energy_replenished_date == today:
        return False
    current = user.energy_balance or 0
    user.energy_balance = min(current + ENERGY_DAILY_SUBSCRIBER, ENERGY_MAX_SUBSCRIBER)
    user.energy_replenished_date = today
    return True
