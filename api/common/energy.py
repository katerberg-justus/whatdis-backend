from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func, cast, Date as SADate
from api import db, cache
from api.common.limits import (
    ENERGY_DAILY_ANONYMOUS,
    ENERGY_DAILY_USER,
    ENERGY_DAILY_SUBSCRIBER,
    ENERGY_MAX_SUBSCRIBER,
)


def _seconds_until_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def _anon_key(ip: str) -> str:
    return f"energy:anon:{ip}"


def _user_key(user_id: str) -> str:
    return f"energy:user:{user_id}"


def _count_todays_guesses(user_id: str) -> int:
    from api.models.guess import Guess
    from api.models.battle_guess import BattleGuess
    today = date.today()
    solo = db.session.execute(
        db.select(func.count()).select_from(Guess).where(
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
    return solo + battle


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
        _maybe_replenish(user)
        return user.energy_balance or 0
    cached = _cached_user_energy(user.id)
    if cached is not None:
        return cached
    remaining = max(0, ENERGY_DAILY_USER - _count_todays_guesses(user.id))
    _set_user_energy_cache(user.id, remaining)
    return remaining


def consume_energy(user, ip: str | None = None) -> tuple[bool, int]:
    """
    Attempt to consume 1 energy.
    Returns (allowed, energy_remaining_after_consumption).
    Must be called before the guess is committed.
    """
    if user is None:
        return _consume_anon(ip)
    if user.is_subscribed:
        return _consume_subscriber(user)
    return _consume_user(user)


# ── Per-tier implementations ──────────────────────────────────────────────────

def _consume_anon(ip: str) -> tuple[bool, int]:
    key = _anon_key(ip)
    remaining = cache.get(key)
    if remaining is None:
        remaining = ENERGY_DAILY_ANONYMOUS
    if remaining <= 0:
        return False, 0
    remaining -= 1
    cache.set(key, remaining, timeout=_seconds_until_midnight())
    return True, remaining


def _consume_user(user) -> tuple[bool, int]:
    cached = _cached_user_energy(user.id)
    if cached is not None:
        remaining = cached
    else:
        remaining = max(0, ENERGY_DAILY_USER - _count_todays_guesses(user.id))
    if remaining <= 0:
        return False, 0
    # Write the post-consumption value — guess is committed by the caller
    _set_user_energy_cache(user.id, remaining - 1)
    return True, remaining - 1


def _consume_subscriber(user) -> tuple[bool, int]:
    _maybe_replenish(user)
    balance = user.energy_balance or 0
    if balance <= 0:
        return False, 0
    user.energy_balance = balance - 1
    # caller commits the session together with the guess
    return True, user.energy_balance


def _maybe_replenish(user) -> None:
    today = date.today()
    if user.energy_replenished_date == today:
        return
    current = user.energy_balance or 0
    user.energy_balance = min(current + ENERGY_DAILY_SUBSCRIBER, ENERGY_MAX_SUBSCRIBER)
    user.energy_replenished_date = today
