"""
Gamification logic for PancrePal.
Handles streaks, badges, and daily tips.
"""

from datetime import datetime, date, timedelta
from db import db, UserProgress, BADGES
import random


def update_streak(user_id: int, log_date: date):
    """
    Update user's streak based on new log entry.

    Args:
        user_id: User ID
        log_date: Date of the log entry (as date object)
    """
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        return

    # Increment total logs
    progress.total_logs += 1

    # Update streak logic
    if progress.last_log_date is None:
        # First ever log
        progress.current_streak = 1
        progress.longest_streak = 1
    else:
        days_since_last = (log_date - progress.last_log_date).days

        if days_since_last == 0:
            # Same day - no streak change
            pass
        elif days_since_last == 1:
            # Consecutive day - increment streak
            progress.current_streak += 1
            if progress.current_streak > progress.longest_streak:
                progress.longest_streak = progress.current_streak
        else:
            # Streak broken - reset to 1
            progress.current_streak = 1

    # Update last log date
    progress.last_log_date = log_date

    db.session.commit()


def check_and_award_badges(progress: UserProgress) -> list:
    """
    Check if user has earned any new badges.

    Args:
        progress: UserProgress object

    Returns:
        List of newly earned badge dictionaries
    """
    newly_earned = []

    # Check each badge condition
    badge_conditions = [
        ('first_log', progress.total_logs >= 1),
        ('streak_3', progress.current_streak >= 3),
        ('streak_7', progress.current_streak >= 7),
        ('streak_30', progress.current_streak >= 30),
        ('logs_50', progress.total_logs >= 50),
        ('logs_100', progress.total_logs >= 100),
    ]

    for badge_id, condition in badge_conditions:
        if condition and not progress.has_badge(badge_id):
            progress.add_badge(badge_id)
            newly_earned.append(BADGES[badge_id])

    if newly_earned:
        db.session.commit()

    return newly_earned


def get_daily_tip() -> dict:
    """
    Get a random daily tip for the dashboard.

    Returns:
        Dictionary with tip text and category
    """
    tips = [
        {
            'tip': 'Try logging at the same times each day to spot patterns more easily.',
            'category': 'consistency'
        },
        {
            'tip': 'Tracking your mood helps identify emotional triggers for high or low glucose.',
            'category': 'mood'
        },
        {
            'tip': 'Logging carbs alongside glucose can reveal how different foods affect you.',
            'category': 'carbs'
        },
        {
            'tip': 'Small consistent habits matter more than perfect readings. Keep going!',
            'category': 'motivation'
        },
        {
            'tip': 'Notice any patterns? Share your PancrePal reports with your diabetes team.',
            'category': 'collaboration'
        },
        {
            'tip': 'Exercise can affect glucose for hours. Log your workouts in the notes field!',
            'category': 'exercise'
        },
        {
            'tip': 'Morning readings help establish your baseline glucose levels.',
            'category': 'timing'
        },
        {
            'tip': 'Stress affects blood glucose. Try some deep breathing when levels spike.',
            'category': 'stress'
        },
        {
            'tip': 'Celebrate small wins! Every log entry is a step toward better management.',
            'category': 'motivation'
        },
        {
            'tip': 'Your time-in-range percentage is the most important metric. Aim for 70%+!',
            'category': 'metrics'
        }
    ]

    return random.choice(tips)


def should_show_reminder(user_id: int) -> dict:
    """
    Check if user should see a gentle reminder to log.

    Args:
        user_id: User ID

    Returns:
        Dictionary with reminder info or None
    """
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress or not progress.last_log_date:
        return None

    # Check if user hasn't logged today
    today = datetime.now().date()
    days_since_last = (today - progress.last_log_date).days

    if days_since_last >= 1:
        return {
            'show': True,
            'message': f"It's been {days_since_last} day{'s' if days_since_last > 1 else ''} since your last log. Keep your streak going!",
            'days': days_since_last
        }

    return None