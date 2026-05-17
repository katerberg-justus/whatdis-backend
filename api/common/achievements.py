"""
Check and award achievements after game events.
All functions are fire-and-forget: errors are swallowed so they never
block the guess response.
"""
from datetime import date
from sqlalchemy import select
from api import db


def _counter(user, field: str) -> int:
    return int(getattr(user, field, 0) or 0)


def _increment_counter(user, field: str, amount: int = 1) -> int:
    value = _counter(user, field) + amount
    setattr(user, field, value)
    return value


def _update_streak(user) -> None:
    today = date.today()
    if user.streak_updated_date == today:
        return
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    if user.streak_updated_date == yesterday:
        user.current_streak = (user.current_streak or 0) + 1
    else:
        user.current_streak = 1
    user.streak_updated_date = today


def _award_category(user_id: str, category: str, count: int) -> list:
    from api.models.achievement import Achievement
    from api.models.user_achievement import UserAchievement

    candidates = db.session.execute(
        select(Achievement).where(
            Achievement.category == category,
            Achievement.threshold <= count,
        )
    ).scalars().all()
    if not candidates:
        return []

    already_earned = {
        row[0] for row in db.session.execute(
            select(UserAchievement.achievement_id).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id.in_([a.id for a in candidates]),
            )
        ).all()
    }

    newly_earned = []
    for achievement in candidates:
        if achievement.id not in already_earned:
            db.session.add(UserAchievement(user_id=user_id, achievement_id=achievement.id))
            newly_earned.append(achievement)
    return newly_earned


def _serialize_new(achievements: list) -> list:
    return [
        {"id": a.id, "category": a.category, "name": a.name, "icon": a.icon}
        for a in achievements
    ]


def check_after_guess(user, won: bool = False) -> list:
    """Call after a guess is committed. Updates streak and awards achievements.
    Returns newly-earned achievements (serialized) for surfacing to the client.
    """
    try:
        user_id = user.id
        _update_streak(user)

        newly: list = []
        guess_count = _increment_counter(user, "total_guess_count")
        newly += _award_category(user_id, "guesses", guess_count)
        from api.common.energy import award_referral_bonus_if_eligible
        award_referral_bonus_if_eligible(user)

        if won:
            win_count = _increment_counter(user, "win_count")
            newly += _award_category(user_id, "wins", win_count)

        newly += _award_category(user_id, "streak", user.current_streak or 0)

        db.session.flush()
        return _serialize_new(newly)
    except Exception:
        db.session.rollback()
        return []


def check_after_battle_guess(user, won: bool = False, opponent=None) -> list:
    """Call after a battle guess is committed. Returns newly-earned achievements."""
    try:
        user_id = user.id
        _update_streak(user)

        newly: list = []
        guess_count = _increment_counter(user, "total_guess_count")
        newly += _award_category(user_id, "guesses", guess_count)
        from api.common.energy import award_referral_bonus_if_eligible
        award_referral_bonus_if_eligible(user)

        if won:
            battle_wins = _increment_counter(user, "battle_win_count")
            newly += _award_category(user_id, "battle_won", battle_wins)
            battles_played = _increment_counter(user, "battle_played_count")
            newly += _award_category(user_id, "battle_played", battles_played)
            if opponent is not None:
                _increment_counter(opponent, "battle_played_count")

        newly += _award_category(user_id, "streak", user.current_streak or 0)

        db.session.flush()
        return _serialize_new(newly)
    except Exception:
        db.session.rollback()
        return []


def check_after_daily(user) -> list:
    """Call after a daily challenge game is completed. Returns newly-earned achievements."""
    try:
        daily_count = _increment_counter(user, "daily_completion_count")
        newly = _award_category(user.id, "daily", daily_count)
        db.session.flush()
        return _serialize_new(newly)
    except Exception:
        db.session.rollback()
        return []


def record_hint(user) -> None:
    """Record a hint in the lifetime guess counter without awarding immediately."""
    if user is not None:
        _increment_counter(user, "total_guess_count")
