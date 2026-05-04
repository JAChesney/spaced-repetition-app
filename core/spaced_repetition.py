"""
SM-2 spaced repetition algorithm.
quality: 0=Again, 1=Hard, 2=Good, 3=Easy
"""
from datetime import date, timedelta
from .models import CardProgress


def review(progress: CardProgress, quality: int) -> CardProgress:
    """Return updated CardProgress after a review. Does not persist."""
    ef = progress.ease_factor
    reps = progress.repetitions
    interval = progress.interval_days

    if quality == 0:  # Again — reset
        reps = 0
        interval = 1
    elif quality == 1:  # Hard
        ef = max(1.3, ef - 0.15)
        interval = max(1, round(interval * 1.2)) if reps > 0 else 1
        reps += 1
    elif quality == 2:  # Good
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = round(interval * ef)
        reps += 1
    else:  # Easy (quality == 3)
        ef = min(3.0, ef + 0.15)
        if reps == 0:
            interval = 3
        elif reps == 1:
            interval = 5
        else:
            interval = round(interval * ef * 1.3)
        reps += 1

    progress.ease_factor = round(ef, 2)
    progress.interval_days = max(1, interval)
    progress.repetitions = reps
    progress.next_review_date = date.today() + timedelta(days=progress.interval_days)
    return progress
