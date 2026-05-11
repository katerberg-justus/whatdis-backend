import os

# Maximum guesses allowed per game session by tier
GUESS_LIMIT_ANONYMOUS  = int(os.getenv("GUESS_LIMIT_ANONYMOUS",   15))
GUESS_LIMIT_USER       = int(os.getenv("GUESS_LIMIT_USER",        30))
GUESS_LIMIT_SUBSCRIBER = int(os.getenv("GUESS_LIMIT_SUBSCRIBER", 100))

# How many distinct daily challenges a player may start per calendar day
DAILY_LIMIT_ANONYMOUS  = int(os.getenv("DAILY_LIMIT_ANONYMOUS",  1))
DAILY_LIMIT_USER       = int(os.getenv("DAILY_LIMIT_USER",       1))
DAILY_LIMIT_SUBSCRIBER = int(os.getenv("DAILY_LIMIT_SUBSCRIBER", 8))  # all 8 slots

# Energy — global daily guess budget across all games
ENERGY_DAILY_ANONYMOUS  = int(os.getenv("ENERGY_DAILY_ANONYMOUS",   10))
ENERGY_DAILY_USER       = int(os.getenv("ENERGY_DAILY_USER",        30))
ENERGY_DAILY_SUBSCRIBER = int(os.getenv("ENERGY_DAILY_SUBSCRIBER", 500))
ENERGY_MAX_SUBSCRIBER   = int(os.getenv("ENERGY_MAX_SUBSCRIBER",   500))


def guess_limit_for(user) -> int:
    """Return the guess cap for a User instance (or None for anonymous)."""
    if user is None:
        return GUESS_LIMIT_ANONYMOUS
    if user.is_subscribed:
        return GUESS_LIMIT_SUBSCRIBER
    return GUESS_LIMIT_USER


def daily_limit_for(user) -> int:
    if user is None:
        return DAILY_LIMIT_ANONYMOUS
    if user.is_subscribed:
        return DAILY_LIMIT_SUBSCRIBER
    return DAILY_LIMIT_USER
