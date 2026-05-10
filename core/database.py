"""
Repository layer. Swap SQLiteRepository for a Supabase/S3 implementation
by implementing the same AbstractRepository interface.
"""
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional
from .models import MCQ, CardProgress, ReviewLog


class AbstractRepository(ABC):
    @abstractmethod
    def add_mcq(self, mcq: MCQ) -> MCQ: ...

    @abstractmethod
    def update_mcq(self, mcq: MCQ) -> MCQ: ...

    @abstractmethod
    def delete_mcq(self, mcq_id: int) -> None: ...

    @abstractmethod
    def get_mcq(self, mcq_id: int) -> Optional[MCQ]: ...

    @abstractmethod
    def list_mcqs(self, subject: str = "", topic: str = "", search: str = "",
                  limit: int = 0, offset: int = 0) -> list[MCQ]: ...

    @abstractmethod
    def count_mcqs(self, subject: str = "", topic: str = "", search: str = "") -> int: ...

    @abstractmethod
    def get_due_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]: ...

    @abstractmethod
    def get_new_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]: ...

    @abstractmethod
    def get_subject_stats(self) -> list[dict]: ...

    @abstractmethod
    def get_topic_stats(self, subject: str) -> list[dict]: ...

    @abstractmethod
    def get_recent_subject_activity(self, limit: int = 3) -> list[dict]: ...

    @abstractmethod
    def get_progress(self, mcq_id: int) -> Optional[CardProgress]: ...

    @abstractmethod
    def save_progress(self, progress: CardProgress) -> CardProgress: ...

    @abstractmethod
    def add_review_log(self, log: ReviewLog) -> ReviewLog: ...

    @abstractmethod
    def get_stats(self) -> dict: ...

    @abstractmethod
    def list_subjects(self) -> list[str]: ...

    @abstractmethod
    def list_topics(self, subject: str = "") -> list[str]: ...


class SQLiteRepository(AbstractRepository):
    def __init__(self, db_path: str = "mcqs.db"):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS mcqs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A','B','C','D')),
                    subject TEXT DEFAULT '',
                    topic TEXT DEFAULT '',
                    explanation TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS card_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mcq_id INTEGER UNIQUE NOT NULL REFERENCES mcqs(id) ON DELETE CASCADE,
                    ease_factor REAL DEFAULT 2.5,
                    interval_days INTEGER DEFAULT 0,
                    repetitions INTEGER DEFAULT 0,
                    next_review_date TEXT DEFAULT (date('now')),
                    last_reviewed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS review_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mcq_id INTEGER NOT NULL REFERENCES mcqs(id) ON DELETE CASCADE,
                    quality INTEGER NOT NULL,
                    was_correct INTEGER NOT NULL,
                    reviewed_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_mcqs_subject ON mcqs(subject);
                CREATE INDEX IF NOT EXISTS idx_mcqs_topic ON mcqs(topic);
                CREATE INDEX IF NOT EXISTS idx_mcqs_subject_topic ON mcqs(subject, topic);
                CREATE INDEX IF NOT EXISTS idx_cp_next_review ON card_progress(next_review_date);
                CREATE INDEX IF NOT EXISTS idx_rl_reviewed_at ON review_logs(reviewed_at);
            """)

    # --- MCQ CRUD ---

    def add_mcq(self, mcq: MCQ) -> MCQ:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO mcqs (question, option_a, option_b, option_c, option_d,
                   correct_answer, subject, topic, explanation)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.explanation),
            )
            mcq.id = cur.lastrowid
            mcq.created_at = datetime.now()
        return mcq

    def update_mcq(self, mcq: MCQ) -> MCQ:
        with self._conn() as conn:
            conn.execute(
                """UPDATE mcqs SET question=?, option_a=?, option_b=?, option_c=?,
                   option_d=?, correct_answer=?, subject=?, topic=?, explanation=?
                   WHERE id=?""",
                (mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.explanation, mcq.id),
            )
        return mcq

    def delete_mcq(self, mcq_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM mcqs WHERE id=?", (mcq_id,))

    def get_mcq(self, mcq_id: int) -> Optional[MCQ]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM mcqs WHERE id=?", (mcq_id,)).fetchone()
        return self._row_to_mcq(row) if row else None

    def list_mcqs(self, subject: str = "", topic: str = "", search: str = "",
                  limit: int = 0, offset: int = 0) -> list[MCQ]:
        sql, params = self._mcqs_filter_sql(subject, topic, search)
        sql += " ORDER BY created_at DESC"
        if limit:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def count_mcqs(self, subject: str = "", topic: str = "", search: str = "") -> int:
        sql, params = self._mcqs_filter_sql(subject, topic, search)
        sql = sql.replace("SELECT *", "SELECT COUNT(*)", 1)
        with self._conn() as conn:
            return conn.execute(sql, params).fetchone()[0]

    @staticmethod
    def _mcqs_filter_sql(subject: str, topic: str, search: str):
        sql = "SELECT * FROM mcqs WHERE 1=1"
        params: list = []
        if subject:
            sql += " AND subject=?"
            params.append(subject)
        if topic:
            sql += " AND topic=?"
            params.append(topic)
        if search:
            sql += (" AND (question LIKE ? OR option_a LIKE ? OR option_b LIKE ?"
                    " OR option_c LIKE ? OR option_d LIKE ? OR subject LIKE ? OR topic LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like, like, like, like, like])
        return sql, params

    def get_due_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]:
        today = date.today().isoformat()
        sql = """SELECT m.* FROM mcqs m
                 JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE cp.next_review_date <= ? AND cp.repetitions > 0"""
        params: list = [today]
        if subject:
            sql += " AND m.subject=?"
            params.append(subject)
        if topic:
            sql += " AND m.topic=?"
            params.append(topic)
        sql += " ORDER BY cp.next_review_date ASC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def get_new_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]:
        sql = """SELECT m.* FROM mcqs m
                 LEFT JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE (cp.mcq_id IS NULL OR cp.repetitions = 0)"""
        params: list = []
        if subject:
            sql += " AND m.subject=?"
            params.append(subject)
        if topic:
            sql += " AND m.topic=?"
            params.append(topic)
        sql += " ORDER BY m.created_at ASC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def get_subject_stats(self) -> list[dict]:
        today = date.today().isoformat()
        with self._conn() as conn:
            subjects = [r[0] for r in conn.execute(
                "SELECT DISTINCT subject FROM mcqs WHERE subject != '' ORDER BY subject"
            ).fetchall()]
            result = []
            for subj in subjects:
                total = conn.execute(
                    "SELECT COUNT(*) FROM mcqs WHERE subject=?", (subj,)
                ).fetchone()[0]
                due = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND cp.next_review_date<=? AND cp.repetitions>0""",
                    (subj, today),
                ).fetchone()[0]
                mastered = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND cp.repetitions>=3 AND cp.ease_factor>=2.0""",
                    (subj,),
                ).fetchone()[0]
                topics = conn.execute(
                    "SELECT COUNT(DISTINCT topic) FROM mcqs WHERE subject=? AND topic!=''",
                    (subj,),
                ).fetchone()[0]
                result.append({
                    "subject": subj, "total": total, "due": due,
                    "mastered": mastered, "topics": topics,
                    "mastery_pct": round(mastered / total * 100) if total else 0,
                })
        return result

    def get_topic_stats(self, subject: str) -> list[dict]:
        today = date.today().isoformat()
        with self._conn() as conn:
            topics = [r[0] for r in conn.execute(
                "SELECT DISTINCT topic FROM mcqs WHERE subject=? AND topic!='' ORDER BY topic",
                (subject,),
            ).fetchall()]
            result = []
            for tpc in topics:
                total = conn.execute(
                    "SELECT COUNT(*) FROM mcqs WHERE subject=? AND topic=?", (subject, tpc)
                ).fetchone()[0]
                due = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND m.topic=? AND cp.next_review_date<=? AND cp.repetitions>0""",
                    (subject, tpc, today),
                ).fetchone()[0]
                mastered = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND m.topic=? AND cp.repetitions>=3 AND cp.ease_factor>=2.0""",
                    (subject, tpc),
                ).fetchone()[0]
                result.append({
                    "topic": tpc, "total": total, "due": due,
                    "mastered": mastered,
                    "mastery_pct": round(mastered / total * 100) if total else 0,
                })
        return result

    def get_recent_subject_activity(self, limit: int = 3) -> list[dict]:
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT m.subject, MAX(rl.reviewed_at) as last_activity
                   FROM review_logs rl JOIN mcqs m ON m.id=rl.mcq_id
                   WHERE m.subject != ''
                   GROUP BY m.subject
                   ORDER BY last_activity DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            if not rows:
                rows2 = conn.execute(
                    """SELECT subject, datetime('now') as last_activity
                       FROM mcqs WHERE subject != ''
                       GROUP BY subject ORDER BY COUNT(*) DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
                subjects = [r[0] for r in rows2]
            else:
                subjects = [r[0] for r in rows]

            result = []
            for subj in subjects:
                total = conn.execute(
                    "SELECT COUNT(*) FROM mcqs WHERE subject=?", (subj,)
                ).fetchone()[0]
                due = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND cp.next_review_date<=? AND cp.repetitions>0""",
                    (subj, today),
                ).fetchone()[0]
                mastered = conn.execute(
                    """SELECT COUNT(*) FROM mcqs m JOIN card_progress cp ON cp.mcq_id=m.id
                       WHERE m.subject=? AND cp.repetitions>=3 AND cp.ease_factor>=2.0""",
                    (subj,),
                ).fetchone()[0]
                result.append({
                    "subject": subj, "total": total, "due": due,
                    "mastery_pct": round(mastered / total * 100) if total else 0,
                })
        return result

    # --- Progress ---

    def get_progress(self, mcq_id: int) -> Optional[CardProgress]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM card_progress WHERE mcq_id=?", (mcq_id,)
            ).fetchone()
        return self._row_to_progress(row) if row else None

    def save_progress(self, progress: CardProgress) -> CardProgress:
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM card_progress WHERE mcq_id=?", (progress.mcq_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE card_progress SET ease_factor=?, interval_days=?,
                       repetitions=?, next_review_date=?, last_reviewed_at=?
                       WHERE mcq_id=?""",
                    (progress.ease_factor, progress.interval_days, progress.repetitions,
                     progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None,
                     progress.mcq_id),
                )
                progress.id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO card_progress
                       (mcq_id, ease_factor, interval_days, repetitions, next_review_date, last_reviewed_at)
                       VALUES (?,?,?,?,?,?)""",
                    (progress.mcq_id, progress.ease_factor, progress.interval_days,
                     progress.repetitions, progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None),
                )
                progress.id = cur.lastrowid
        return progress

    # --- Review logs ---

    def add_review_log(self, log: ReviewLog) -> ReviewLog:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO review_logs (mcq_id, quality, was_correct, reviewed_at) VALUES (?,?,?,?)",
                (log.mcq_id, log.quality, int(log.was_correct), log.reviewed_at.isoformat()),
            )
            log.id = cur.lastrowid
        return log

    # --- Stats & metadata ---

    def get_stats(self) -> dict:
        today = date.today().isoformat()
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM mcqs").fetchone()[0]
            due = conn.execute(
                """SELECT COUNT(*) FROM card_progress
                   WHERE next_review_date <= ? AND repetitions > 0""",
                (today,),
            ).fetchone()[0]
            new = conn.execute(
                """SELECT COUNT(*) FROM mcqs m
                   LEFT JOIN card_progress cp ON cp.mcq_id = m.id
                   WHERE cp.mcq_id IS NULL OR cp.repetitions = 0""",
            ).fetchone()[0]
            reviewed_today = conn.execute(
                "SELECT COUNT(*) FROM review_logs WHERE date(reviewed_at)=?", (today,)
            ).fetchone()[0]
        return {"total": total, "due": due, "new": new, "reviewed_today": reviewed_today}

    def list_subjects(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT subject FROM mcqs WHERE subject != '' ORDER BY subject"
            ).fetchall()
        return [r[0] for r in rows]

    def list_topics(self, subject: str = "") -> list[str]:
        sql = "SELECT DISTINCT topic FROM mcqs WHERE topic != ''"
        params: list = []
        if subject:
            sql += " AND subject=?"
            params.append(subject)
        sql += " ORDER BY topic"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [r[0] for r in rows]

    # --- Row mappers ---

    @staticmethod
    def _row_to_mcq(row) -> MCQ:
        return MCQ(
            id=row["id"],
            question=row["question"],
            option_a=row["option_a"],
            option_b=row["option_b"],
            option_c=row["option_c"],
            option_d=row["option_d"],
            correct_answer=row["correct_answer"],
            subject=row["subject"],
            topic=row["topic"],
            explanation=row["explanation"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    @staticmethod
    def _row_to_progress(row) -> CardProgress:
        return CardProgress(
            id=row["id"],
            mcq_id=row["mcq_id"],
            ease_factor=row["ease_factor"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            next_review_date=date.fromisoformat(row["next_review_date"]),
            last_reviewed_at=datetime.fromisoformat(row["last_reviewed_at"])
            if row["last_reviewed_at"] else None,
        )
