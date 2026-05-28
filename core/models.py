from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class MCQ:
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str          # "A", "B", "C", or "D"
    subject: str = ""
    topic: str = ""
    subtopic: str = ""           # optional
    explanation: str = ""
    question_type: str = "STATIC"   # "STATIC", "CURRENT_AFFAIRS", or "BIHAR_GK"
    event_date: Optional[date] = None  # for CURRENT_AFFAIRS only
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class CardProgress:
    mcq_id: int
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    next_review_date: date = field(default_factory=date.today)
    last_reviewed_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class ReviewLog:
    mcq_id: int
    quality: int       # 0=Again, 1=Hard, 2=Good, 3=Easy
    was_correct: bool
    reviewed_at: datetime = field(default_factory=datetime.now)
    id: Optional[int] = None
