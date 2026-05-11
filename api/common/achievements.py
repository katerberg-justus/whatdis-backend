"""
Check and award achievements after game events.
All functions are fire-and-forget: errors are swallowed so they never
block the guess response.
"""
from datetime import date
from sqlalchemy import func, cast, select
from sqlalchemy.dialects.mysql import CHAR
from api import db


def _count_guesses(user_id: str) -> int:
    from api.models.guess import Guess
    from api.models.battle_guess import BattleGuess
    solo = db.session.execute(
        select(func.count()).select_from(Guess).where(Guess.user_id == user_id)
    ).scalar_one()
    battle = db.session.execute(
        select(func.count()).select_from(BattleGuess).where(BattleGuess.user_id == user_id)
    ).scalar_one()
    return solo + battle


def _count_wins(user_id: str) -> int:
    from api.models.game import Game
    return db.session.execute(
        select(func.count()).select_from(Game).where(
            Game.user_id == user_id,
            Game.completed_at.isnot(None),
        )
    ).scalar_one()


def _count_daily_completions(user_id: str) -> int:
    from api.models.game import Game
    from api.models.daily_challenge import DailyChallenge
    from api.models.challenge import Challenge
    daily_challenge_ids = select(Challenge.id).join(
        DailyChallenge, DailyChallenge.challenge_id == Challenge.id
    )
    return db.session.execute(
        select(func.count()).select_from(Game).where(
            Game.user_id == user_id,
            Game.completed_at.isnot(None),
            Game.challenge_id.in_(daily_challenge_ids),
        )
    ).scalar_one()


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


def check_after_guess(user, won: bool = False) -> None:
    """Call after a guess is committed. Updates streak and awards achievements."""
    try:
        user_id = user.id
        _update_streak(user)

        guess_count = _count_guesses(user_id)
        _award_category(user_id, "guesses", guess_count)

        if won:
            win_count = _count_wins(user_id)
            _award_category(user_id, "wins", win_count)

        _award_category(user_id, "streak", user.current_streak or 0)

        db.session.flush()
    except Exception:
        db.session.rollback()


def check_after_daily(user) -> None:
    """Call after a daily challenge game is completed."""
    try:
        daily_count = _count_daily_completions(user.id)
        _award_category(user.id, "daily", daily_count)
        db.session.flush()
    except Exception:
        db.session.rollback()
