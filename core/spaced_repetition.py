"""
Fixed-interval spaced repetition.
quality: 0=Again, 1=Hard, 2=Good, 3=Easy
"""
from datetime import date, timedelta
from .models import CardProgress

_INTERVALS = {0: 1, 1: 2, 2: 3, 3: 4}


def review(progress: CardProgress, quality: int) -> CardProgress:
    """Return updated CardProgress after a review. Does not persist."""
    if quality == 0:  # Again — requeue in session; save as 1 day so it resurfaces tomorrow if session ends
        progress.repetitions = 0
    else:
        progress.repetitions += 1

    progress.interval_days = _INTERVALS[quality]
    progress.next_review_date = date.today() + timedelta(days=progress.interval_days)
    return progress
