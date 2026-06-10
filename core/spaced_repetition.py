"""
Fixed-interval spaced repetition.
quality: 0=Again, 1=Hard, 2=Good, 3=Easy
"""
from datetime import datetime, timedelta, date
from .models import CardProgress

_INTERVALS = {1: 1, 2: 2, 3: 3}   # Hard=1 day, Good=2 days, Easy=3 days


def review(progress: CardProgress, quality: int) -> CardProgress:
    """Return updated CardProgress after a review. Does not persist."""
    if quality == 0:  # Again — card enters review pool immediately; shown only after normal queue clears
        progress.repetitions = 0
        progress.interval_days = 0
        progress.next_review_date = datetime.now()
    else:
        progress.repetitions += 1
        progress.interval_days = _INTERVALS[quality]
        # Schedule to midnight of the target calendar day so Hard=tomorrow,
        # Good=day-after-tomorrow, Easy=3 days from today, regardless of review time.
        target_day = date.today() + timedelta(days=progress.interval_days)
        progress.next_review_date = datetime.combine(target_day, datetime.min.time())
    return progress
