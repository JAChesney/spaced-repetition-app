"""
Fixed-interval spaced repetition.
quality: 0=Again, 1=Hard, 2=Good, 3=Easy
"""
from datetime import datetime, timedelta, time
from .models import CardProgress

_INTERVALS = {1: 1, 2: 2, 3: 3}  # Hard=1 day, Good=2 days, Easy=3 days

# Cycle driven by progress.again_count (persisted across sessions):
# again_count % 3 == 1 → instant requeue in session (DB fallback = 10 min)
# again_count % 3 == 2 → 10 min  (capped to midnight if it crosses day boundary)
# again_count % 3 == 0 → 6 hours (capped to midnight if it crosses day boundary)
_AGAIN_DELTAS = {1: timedelta(minutes=10), 2: timedelta(minutes=10), 0: timedelta(hours=6)}


def _schedule_again(delta: timedelta) -> datetime:
    """Return now+delta, but capped to midnight if the result is tomorrow or later.

    This ensures a card missed past midnight joins tomorrow's normal queue
    rather than appearing in the middle of the night.
    """
    candidate = datetime.now() + delta
    today = datetime.now().date()
    if candidate.date() > today:
        return datetime.combine(candidate.date(), time.min)
    return candidate


def review(progress: CardProgress, quality: int) -> CardProgress:
    """Return updated CardProgress after a review. Does not persist."""
    if quality == 0:  # Again
        progress.again_count += 1
        progress.repetitions = 0
        progress.interval_days = 0
        progress.next_review_date = _schedule_again(_AGAIN_DELTAS[progress.again_count % 3])
    else:
        progress.again_count = 0  # reset cycle on successful review
        progress.repetitions += 1
        progress.interval_days = _INTERVALS[quality]
        progress.next_review_date = datetime.now() + timedelta(days=progress.interval_days)
    return progress
