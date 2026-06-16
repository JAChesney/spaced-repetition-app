"""
Fixed-interval spaced repetition.
quality: 0=Again, 1=Hard, 2=Good, 3=Easy
"""
from datetime import datetime, timedelta, date
from .models import CardProgress

_INTERVALS = {1: 1, 2: 2, 3: 3}   # Hard=1 day, Good=2 days, Easy=3 days (first correct review in a streak)
_EASY_STREAK_DAYS = 7              # Easy, on the 2nd+ consecutive correct review since the last Again


def review(progress: CardProgress, quality: int) -> CardProgress:
    """Return updated CardProgress after a review. Does not persist."""
    if quality == 0:  # Again — card enters review pool immediately; shown only after normal queue clears
        progress.repetitions = 0
        progress.interval_days = 0
        progress.next_review_date = datetime.now()
    else:
        on_streak = progress.repetitions >= 1  # already had a correct review since the last Again
        progress.repetitions += 1
        if quality == 3 and on_streak:
            progress.interval_days = _EASY_STREAK_DAYS
        else:
            progress.interval_days = _INTERVALS[quality]
        # Schedule to midnight of the target calendar day so Hard=tomorrow,
        # Good=day-after-tomorrow, Easy=3 (or 7) days from today, regardless of review time.
        target_day = date.today() + timedelta(days=progress.interval_days)
        progress.next_review_date = datetime.combine(target_day, datetime.min.time())
    return progress
