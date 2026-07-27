"""
Repository layer. Swap SQLiteRepository for a Supabase/S3 implementation
by implementing the same AbstractRepository interface.
"""
import secrets
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional
from .models import MCQ, CardProgress, ReviewLog

# Unambiguous alphanumeric charset — no 0/O or 1/I — for human-typed public IDs.
_PUBLIC_ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _generate_public_id(length: int = 8) -> str:
    return "".join(secrets.choice(_PUBLIC_ID_ALPHABET) for _ in range(length))


# ── Minimal Supabase REST client ──────────────────────────────────────────────
# Pure httpx — no native extensions, bundles cleanly on Android.

class _Table:
    """PostgREST query builder that mirrors the supabase-py interface."""

    def __init__(self, base_url: str, name: str, headers: dict):
        self._url = f"{base_url}/rest/v1/{name}"
        self._headers = headers
        self._params: dict = {}
        self._method = "GET"
        self._body = None

    def select(self, columns: str = "*"):
        self._method = "GET"
        self._params["select"] = columns
        return self

    def insert(self, data: dict):
        self._method = "POST"
        self._body = data
        return self

    def update(self, data: dict):
        self._method = "PATCH"
        self._body = data
        return self

    def delete(self):
        self._method = "DELETE"
        return self

    def eq(self, column: str, value):
        self._params[column] = f"eq.{value}"
        return self

    def in_(self, column: str, values: list):
        joined = ",".join(str(v) for v in values)
        self._params[column] = f"in.({joined})"
        return self

    def execute(self):
        import httpx
        _PAGE = 1000
        with httpx.Client(headers=self._headers, timeout=30.0) as http:
            if self._method == "GET":
                # Paginate through all rows — PostgREST caps at max_rows (default 1000)
                # without pagination, so requests beyond that are silently truncated.
                all_data = []
                offset = 0
                while True:
                    resp = http.get(
                        self._url, params=self._params,
                        headers={"Range": f"{offset}-{offset + _PAGE - 1}",
                                 "Range-Unit": "items"},
                    )
                    resp.raise_for_status()
                    page = resp.json() if resp.content else []
                    if isinstance(page, dict):
                        page = [page]
                    all_data.extend(page)
                    if len(page) < _PAGE:
                        break
                    offset += _PAGE
                data = all_data
            elif self._method == "POST":
                resp = http.post(self._url, json=self._body, params=self._params)
                resp.raise_for_status()
                data = resp.json() if resp.content else []
                if isinstance(data, dict):
                    data = [data]
            elif self._method == "PATCH":
                resp = http.patch(self._url, json=self._body, params=self._params)
                resp.raise_for_status()
                data = resp.json() if resp.content else []
                if isinstance(data, dict):
                    data = [data]
            else:
                resp = http.delete(self._url, params=self._params)
                resp.raise_for_status()
                data = resp.json() if resp.content else []
                if isinstance(data, dict):
                    data = [data]

        class _Result:
            pass
        r = _Result()
        r.data = data
        return r


class _SupabaseClient:
    def __init__(self, url: str, key: str):
        self._base = url.rstrip("/")
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def table(self, name: str) -> _Table:
        return _Table(self._base, name, self._headers)


def _norm_dt(val) -> Optional[str]:
    """Strip timezone offset from a Supabase ISO timestamp.

    Keeps the T separator so the result is consistent with Python's
    datetime.isoformat() output and string comparisons work correctly.
    """
    if not val:
        return None
    s = str(val).replace("Z", "+00:00")
    for sep in ("+", "-"):
        idx = s.rfind(sep, 10)
        if idx != -1:
            s = s[:idx]
            break
    return s


def _snap_midnight(dt_str: str) -> str:
    """Snap a future datetime string to midnight of its calendar day.

    Cards should become due at the start of the day, not at the exact time
    they were reviewed.  Past/already-due dates are left unchanged.
    """
    if not dt_str or len(dt_str) < 10:
        return dt_str
    if dt_str <= datetime.now().isoformat():
        return dt_str  # already due — don't touch
    return dt_str[:10] + "T00:00:00"


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
    def get_mcq_by_public_id(self, public_id: str) -> Optional[MCQ]: ...

    @abstractmethod
    def list_mcqs(self, subject: str = "", topic: str = "", search: str = "",
                  limit: int = 0, offset: int = 0) -> list[MCQ]: ...

    @abstractmethod
    def count_mcqs(self, subject: str = "", topic: str = "", search: str = "") -> int: ...

    @abstractmethod
    def get_due_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]: ...

    @abstractmethod
    def get_new_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]: ...

    @abstractmethod
    def get_review_pool_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]: ...

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
    def get_next_due_info(self) -> Optional[dict]: ...

    @abstractmethod
    def list_subjects(self) -> list[str]: ...

    @abstractmethod
    def list_topics(self, subject: str = "") -> list[str]: ...

    @abstractmethod
    def reset_schedule(self) -> None: ...

    @abstractmethod
    def delete_subject(self, subject: str) -> None: ...

    @abstractmethod
    def delete_topic(self, subject: str, topic: str) -> None: ...

    @abstractmethod
    def get_hidden_subjects(self) -> set: ...

    @abstractmethod
    def get_hidden_topics(self) -> set: ...

    @abstractmethod
    def set_subject_hidden(self, subject: str, hidden: bool) -> None: ...

    @abstractmethod
    def set_topic_hidden(self, subject: str, topic: str, hidden: bool) -> None: ...

    def soft_sync(self) -> None:
        """Refresh card_progress from remote without wiping local data.
        No-op for local-only repos; overridden by CachedRepository."""


class SQLiteRepository(AbstractRepository):
    def __init__(self, db_path: str = "mcqs.db"):
        self.db_path = db_path
        self._tls = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._tls.connection = conn
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
                    subtopic TEXT DEFAULT '',
                    explanation TEXT DEFAULT '',
                    question_type TEXT NOT NULL DEFAULT 'STATIC'
                        CHECK(question_type IN ('STATIC','CURRENT_AFFAIRS','BIHAR_GK')),
                    event_date TEXT,
                    public_id TEXT,
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

                CREATE TABLE IF NOT EXISTS hidden_subjects (
                    subject TEXT PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS hidden_topics (
                    subject TEXT NOT NULL,
                    topic   TEXT NOT NULL,
                    PRIMARY KEY (subject, topic)
                );
            """)
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add columns introduced after the initial schema (safe to run on any DB version)."""
        existing_mcqs = {row[1] for row in conn.execute("PRAGMA table_info(mcqs)").fetchall()}
        mcq_migrations = [
            ("subtopic",      "ALTER TABLE mcqs ADD COLUMN subtopic TEXT NOT NULL DEFAULT ''"),
            ("question_type", "ALTER TABLE mcqs ADD COLUMN question_type TEXT NOT NULL DEFAULT 'STATIC'"),
            ("event_date",    "ALTER TABLE mcqs ADD COLUMN event_date TEXT"),
            ("public_id",     "ALTER TABLE mcqs ADD COLUMN public_id TEXT"),
        ]
        for col, sql in mcq_migrations:
            if col not in existing_mcqs:
                conn.execute(sql)

        # Backfill public_id for rows that predate this column, then enforce uniqueness.
        used_ids = {
            r[0] for r in conn.execute(
                "SELECT public_id FROM mcqs WHERE public_id IS NOT NULL AND public_id != ''"
            ).fetchall()
        }
        missing = conn.execute(
            "SELECT id FROM mcqs WHERE public_id IS NULL OR public_id = ''"
        ).fetchall()
        for (mcq_id,) in missing:
            pid = _generate_public_id()
            while pid in used_ids:
                pid = _generate_public_id()
            used_ids.add(pid)
            conn.execute("UPDATE mcqs SET public_id=? WHERE id=?", (pid, mcq_id))
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mcqs_public_id ON mcqs(public_id)")

        existing_cp = {row[1] for row in conn.execute("PRAGMA table_info(card_progress)").fetchall()}
        cp_migrations = [
            ("again_count", "ALTER TABLE card_progress ADD COLUMN again_count INTEGER NOT NULL DEFAULT 0"),
            ("review_tag",  "ALTER TABLE card_progress ADD COLUMN review_tag TEXT NOT NULL DEFAULT ''"),
        ]
        for col, sql in cp_migrations:
            if col not in existing_cp:
                conn.execute(sql)

        # Snap all future next_review_date values to midnight of their calendar day.
        # Fixes cards scheduled with the old rolling-time formula (now + 24h) so they
        # appear at the start of the correct day, not at a random time.
        conn.execute(
            """UPDATE card_progress
               SET next_review_date = substr(next_review_date, 1, 10) || 'T00:00:00'
               WHERE repetitions > 0
                 AND next_review_date > ?
                 AND next_review_date NOT LIKE '%T00:00:00'""",
            (datetime.now().isoformat(),),
        )

    # --- MCQ CRUD ---

    def add_mcq(self, mcq: MCQ) -> MCQ:
        if not mcq.public_id:
            mcq.public_id = self._unique_public_id()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO mcqs (question, option_a, option_b, option_c, option_d,
                   correct_answer, subject, topic, subtopic, explanation,
                   question_type, event_date, public_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.subtopic, mcq.explanation,
                 mcq.question_type,
                 mcq.event_date.isoformat() if mcq.event_date else None,
                 mcq.public_id),
            )
            mcq.id = cur.lastrowid
            mcq.created_at = datetime.now()
        return mcq

    def _unique_public_id(self) -> str:
        with self._conn() as conn:
            while True:
                pid = _generate_public_id()
                if not conn.execute("SELECT 1 FROM mcqs WHERE public_id=?", (pid,)).fetchone():
                    return pid

    def update_mcq(self, mcq: MCQ) -> MCQ:
        with self._conn() as conn:
            conn.execute(
                """UPDATE mcqs SET question=?, option_a=?, option_b=?, option_c=?,
                   option_d=?, correct_answer=?, subject=?, topic=?, subtopic=?,
                   explanation=?, question_type=?, event_date=?
                   WHERE id=?""",
                (mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.subtopic, mcq.explanation,
                 mcq.question_type,
                 mcq.event_date.isoformat() if mcq.event_date else None,
                 mcq.id),
            )
        return mcq

    def delete_mcq(self, mcq_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM mcqs WHERE id=?", (mcq_id,))

    def get_mcq(self, mcq_id: int) -> Optional[MCQ]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM mcqs WHERE id=?", (mcq_id,)).fetchone()
        return self._row_to_mcq(row) if row else None

    def get_mcq_by_public_id(self, public_id: str) -> Optional[MCQ]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM mcqs WHERE public_id=?", (public_id.strip().upper(),)
            ).fetchone()
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
                    " OR option_c LIKE ? OR option_d LIKE ? OR subject LIKE ? OR topic LIKE ?"
                    " OR public_id LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like, like, like, like, like, like])
        return sql, params

    _VISIBLE_FILTER = """
        AND m.subject NOT IN (SELECT subject FROM hidden_subjects)
        AND NOT EXISTS (
            SELECT 1 FROM hidden_topics ht
            WHERE ht.subject = m.subject AND ht.topic = m.topic
        )"""

    def get_due_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        today = datetime.now().isoformat()
        sql = f"""SELECT m.* FROM mcqs m
                 JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE cp.next_review_date <= ? AND cp.repetitions > 0
                   AND (cp.review_tag = '' OR cp.review_tag IS NULL)
                 {self._VISIBLE_FILTER}"""
        params: list = [today]
        if subject:
            sql += " AND m.subject=?"
            params.append(subject)
        if topic:
            sql += " AND m.topic=?"
            params.append(topic)
        sql += " ORDER BY RANDOM()"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def get_new_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        # Only cards never reviewed (no card_progress row).
        # Cards reviewed wrong (repetitions=0, last_reviewed_at IS NOT NULL) are served
        # by get_review_pool_mcqs instead, keeping review cards out of normal sessions.
        sql = f"""SELECT m.* FROM mcqs m
                 LEFT JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE cp.mcq_id IS NULL
                 {self._VISIBLE_FILTER}"""
        params: list = []
        if subject:
            sql += " AND m.subject=?"
            params.append(subject)
        if topic:
            sql += " AND m.topic=?"
            params.append(topic)
        sql += " ORDER BY RANDOM()"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def get_review_pool_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        """Cards tagged 'echo' (wrong once, corrected) or 'drill' (wrong twice), now due."""
        now = datetime.now().isoformat()
        sql = f"""SELECT m.* FROM mcqs m
                 JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE cp.review_tag IN ('echo', 'drill')
                   AND cp.next_review_date <= ?
                 {self._VISIBLE_FILTER}"""
        params: list = [now]
        if subject:
            sql += " AND m.subject=?"
            params.append(subject)
        if topic:
            sql += " AND m.topic=?"
            params.append(topic)
        sql += " ORDER BY RANDOM()"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_mcq(r) for r in rows]

    def get_subject_stats(self) -> list[dict]:
        today = datetime.now().isoformat()
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
        today = datetime.now().isoformat()
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
        today = datetime.now().isoformat()
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
                       repetitions=?, next_review_date=?, last_reviewed_at=?, again_count=?,
                       review_tag=?
                       WHERE mcq_id=?""",
                    (progress.ease_factor, progress.interval_days, progress.repetitions,
                     progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None,
                     progress.again_count, progress.review_tag, progress.mcq_id),
                )
                progress.id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO card_progress
                       (mcq_id, ease_factor, interval_days, repetitions, next_review_date,
                        last_reviewed_at, again_count, review_tag)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (progress.mcq_id, progress.ease_factor, progress.interval_days,
                     progress.repetitions, progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None,
                     progress.again_count, progress.review_tag),
                )
                progress.id = cur.lastrowid
        return progress

    def delete_subject(self, subject: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM mcqs WHERE subject=?", (subject,))
            conn.execute("DELETE FROM hidden_subjects WHERE subject=?", (subject,))
            conn.execute("DELETE FROM hidden_topics WHERE subject=?", (subject,))

    def delete_topic(self, subject: str, topic: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM mcqs WHERE subject=? AND topic=?", (subject, topic))
            conn.execute("DELETE FROM hidden_topics WHERE subject=? AND topic=?", (subject, topic))

    def get_hidden_subjects(self) -> set:
        with self._conn() as conn:
            rows = conn.execute("SELECT subject FROM hidden_subjects").fetchall()
        return {r[0] for r in rows}

    def get_hidden_topics(self) -> set:
        with self._conn() as conn:
            rows = conn.execute("SELECT subject, topic FROM hidden_topics").fetchall()
        return {(r[0], r[1]) for r in rows}

    def set_subject_hidden(self, subject: str, hidden: bool) -> None:
        with self._conn() as conn:
            if hidden:
                conn.execute("INSERT OR IGNORE INTO hidden_subjects (subject) VALUES (?)", (subject,))
            else:
                conn.execute("DELETE FROM hidden_subjects WHERE subject=?", (subject,))

    def set_topic_hidden(self, subject: str, topic: str, hidden: bool) -> None:
        with self._conn() as conn:
            if hidden:
                conn.execute(
                    "INSERT OR IGNORE INTO hidden_topics (subject, topic) VALUES (?,?)",
                    (subject, topic),
                )
            else:
                conn.execute(
                    "DELETE FROM hidden_topics WHERE subject=? AND topic=?",
                    (subject, topic),
                )

    def reset_schedule(self) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute("UPDATE card_progress SET next_review_date=?", (now,))

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
        today = datetime.now().isoformat()
        vf = self._VISIBLE_FILTER
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM mcqs").fetchone()[0]
            due = conn.execute(
                f"""SELECT COUNT(*) FROM card_progress cp
                   JOIN mcqs m ON m.id = cp.mcq_id
                   WHERE cp.next_review_date <= ? AND cp.repetitions > 0 {vf}""",
                (today,),
            ).fetchone()[0]
            new = conn.execute(
                f"""SELECT COUNT(*) FROM mcqs m
                   LEFT JOIN card_progress cp ON cp.mcq_id = m.id
                   WHERE cp.mcq_id IS NULL {vf}""",
            ).fetchone()[0]
            review_pool = conn.execute(
                f"""SELECT COUNT(*) FROM card_progress cp
                   JOIN mcqs m ON m.id = cp.mcq_id
                   WHERE cp.repetitions = 0 AND cp.last_reviewed_at IS NOT NULL
                   AND cp.next_review_date <= ? {vf}""",
                (today,),
            ).fetchone()[0]
            reviewed_today = conn.execute(
                "SELECT COUNT(DISTINCT mcq_id) FROM review_logs WHERE date(reviewed_at)=date(?)", (today,)
            ).fetchone()[0]

            # Retention: % correct in last 7 days
            row7 = conn.execute(
                """SELECT COUNT(*), SUM(was_correct) FROM review_logs
                   WHERE reviewed_at >= datetime(?, '-7 days')""",
                (today,),
            ).fetchone()
            total_7d, correct_7d = row7[0] or 0, row7[1] or 0
            retention_7d = round(correct_7d / total_7d * 100) if total_7d else None

            # Mastered: interval >= 21 days
            mastered = conn.execute(
                "SELECT COUNT(*) FROM card_progress WHERE interval_days >= 21"
            ).fetchone()[0]

            # Streak: consecutive days with at least one review
            dates = [
                r[0] for r in conn.execute(
                    "SELECT DISTINCT date(reviewed_at) FROM review_logs ORDER BY 1 DESC"
                ).fetchall()
            ]
            streak = 0
            from datetime import date as _date, timedelta
            check = _date.today()
            for d in dates:
                if d == str(check):
                    streak += 1
                    check -= timedelta(days=1)
                elif d == str(check - timedelta(days=1)):
                    # allow today not yet studied — count yesterday as start
                    check = _date.fromisoformat(d)
                    streak += 1
                    check -= timedelta(days=1)
                else:
                    break

        return {
            "total": total, "due": due, "new": new,
            "review_pool": review_pool,
            "reviewed_today": reviewed_today,
            "retention_7d": retention_7d,
            "mastered": mastered,
            "streak": streak,
        }

    def get_next_due_info(self) -> Optional[dict]:
        now = datetime.now().isoformat()
        vf = self._VISIBLE_FILTER
        with self._conn() as conn:
            row = conn.execute(
                f"""SELECT MIN(cp.next_review_date) as next_review_date, COUNT(*) as count
                   FROM card_progress cp
                   JOIN mcqs m ON m.id = cp.mcq_id
                   WHERE cp.next_review_date > ? {vf}
                   GROUP BY strftime('%Y-%m-%dT%H', cp.next_review_date)
                   ORDER BY MIN(cp.next_review_date) ASC
                   LIMIT 1""",
                (now,),
            ).fetchone()
        if not row:
            return None
        next_dt = datetime.fromisoformat(row["next_review_date"])
        seconds_until = max(0.0, (next_dt - datetime.now()).total_seconds())
        days_until = (next_dt.date() - date.today()).days
        minutes_until = max(0, int(seconds_until / 60))
        return {
            "days_until": days_until,
            "minutes_until": minutes_until,
            "seconds_until": seconds_until,
            "count": row["count"],
        }

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
        event_date_raw = row["event_date"] if "event_date" in row.keys() else None
        return MCQ(
            id=row["id"],
            question=row["question"],
            option_a=row["option_a"],
            option_b=row["option_b"],
            option_c=row["option_c"],
            option_d=row["option_d"],
            correct_answer=row["correct_answer"],
            subject=row["subject"] or "",
            topic=row["topic"] or "",
            subtopic=row["subtopic"] if "subtopic" in row.keys() else "",
            explanation=row["explanation"] or "",
            question_type=row["question_type"] if "question_type" in row.keys() else "STATIC",
            event_date=date.fromisoformat(event_date_raw) if event_date_raw else None,
            public_id=(row["public_id"] if "public_id" in row.keys() else None) or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    @staticmethod
    def _row_to_progress(row) -> CardProgress:
        keys = row.keys()
        return CardProgress(
            id=row["id"],
            mcq_id=row["mcq_id"],
            ease_factor=row["ease_factor"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            next_review_date=datetime.fromisoformat(row["next_review_date"]),
            last_reviewed_at=datetime.fromisoformat(row["last_reviewed_at"])
            if row["last_reviewed_at"] else None,
            again_count=row["again_count"] if "again_count" in keys else 0,
            review_tag=row["review_tag"] if "review_tag" in keys else "",
        )


class CachedRepository(AbstractRepository):
    """Supabase is the source of truth; SQLite is a local read cache.

    Pulls all data from Supabase into SQLite on every startup.
    All reads go to SQLite (fast, works offline).
    All writes go to Supabase first, then are mirrored to SQLite.
    """

    def __init__(self, supabase_url: str, supabase_key: str, db_path: str = "mcqs.db"):
        self._url = supabase_url
        self._key = supabase_key
        self._sb = _SupabaseClient(supabase_url, supabase_key)
        self._db_path = db_path
        self._local = SQLiteRepository(db_path)
        self.last_sync_error: Optional[str] = None
        try:
            self._sync_from_supabase()
        except Exception as exc:
            self.last_sync_error = str(exc)

    def clear_local_cache_and_sync(self) -> dict:
        """Wipe all local tables and re-sync from Supabase.

        Returns {"fetched": int, "inserted": int, "skipped": int}.
        """
        self.last_sync_error = None
        return self._sync_from_supabase(force=True)

    def _sync_hidden_from_supabase(self) -> None:
        """Pull hidden_subjects + hidden_topics from Supabase into local SQLite.

        Best-effort — silently skips if the tables don't exist yet.
        """
        try:
            hidden_subjs = self._sb.table("hidden_subjects").select("*").execute().data
            hidden_tops  = self._sb.table("hidden_topics").select("*").execute().data
            with self._local._conn() as conn:
                conn.execute("DELETE FROM hidden_subjects")
                conn.execute("DELETE FROM hidden_topics")
                for hs in hidden_subjs:
                    conn.execute(
                        "INSERT OR IGNORE INTO hidden_subjects (subject) VALUES (?)",
                        (hs["subject"],),
                    )
                for ht in hidden_tops:
                    conn.execute(
                        "INSERT OR IGNORE INTO hidden_topics (subject, topic) VALUES (?,?)",
                        (ht["subject"], ht["topic"]),
                    )
        except Exception:
            pass

    def start_hidden_sync_poll(self, on_hidden_change, interval: int = 30) -> None:
        """Poll Supabase every `interval` seconds for hidden state changes.

        Runs in a daemon thread so it stops automatically when the process exits.
        Uses a simple REST call — no WebSocket connections needed.
        """
        import time

        def _poll():
            while True:
                time.sleep(interval)
                try:
                    self._sync_hidden_from_supabase()
                    on_hidden_change()
                except Exception:
                    pass

        threading.Thread(target=_poll, daemon=True).start()

    # ── Sync ─────────────────────────────────────────────────────────────

    def _sync_from_supabase(self, force: bool = False) -> dict:
        """Returns {"fetched": int, "inserted": int, "skipped": int}."""
        mcqs = self._sb.table("mcqs").select("*").execute().data
        progress = self._sb.table("card_progress").select("*").execute().data
        logs = self._sb.table("review_logs").select("*").execute().data

        fetched = len(mcqs)

        # If Supabase is empty but local has data, push local up instead of wiping it
        if not mcqs and self._local.count_mcqs() > 0:
            self._migrate_local_to_supabase()
            return {"fetched": 0, "inserted": 0, "skipped": 0}

        # Snapshot local card_progress before wiping so we can prefer it when
        # it is more recent than Supabase (handles daemon-thread sync not
        # completing before the app was closed).
        local_cp: dict[int, dict] = {}
        if not force:
            with self._local._conn() as snap:
                for row in snap.execute("SELECT * FROM card_progress").fetchall():
                    local_cp[row["mcq_id"]] = {k: row[k] for k in row.keys()}

        inserted = 0
        skipped = 0
        # Rows pulled from Supabase without a public_id (pre-dates the column) get
        # one generated locally now; pushed back to Supabase after the transaction.
        used_public_ids = {m.get("public_id") for m in mcqs if m.get("public_id")}
        backfilled_public_ids: list[tuple[int, str]] = []
        with self._local._conn() as conn:
            # Delete in child-first order to satisfy foreign key constraints
            conn.execute("DELETE FROM review_logs")
            conn.execute("DELETE FROM card_progress")
            conn.execute("DELETE FROM mcqs")
            for m in mcqs:
                try:
                    ans = (m.get("correct_answer") or "").strip().upper()
                    if ans not in ("A", "B", "C", "D"):
                        skipped += 1
                        continue
                    q_type = (m.get("question_type") or "STATIC").strip().upper()
                    if q_type not in ("STATIC", "CURRENT_AFFAIRS", "BIHAR_GK"):
                        q_type = "STATIC"
                    pid = (m.get("public_id") or "").strip()
                    if not pid:
                        pid = _generate_public_id()
                        while pid in used_public_ids:
                            pid = _generate_public_id()
                        used_public_ids.add(pid)
                        backfilled_public_ids.append((m["id"], pid))
                    conn.execute(
                        """INSERT INTO mcqs (id, question, option_a, option_b, option_c, option_d,
                           correct_answer, subject, topic, subtopic, explanation,
                           question_type, event_date, public_id, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (m["id"],
                         m.get("question") or "", m.get("option_a") or "",
                         m.get("option_b") or "", m.get("option_c") or "",
                         m.get("option_d") or "", ans,
                         m.get("subject") or "", m.get("topic") or "",
                         m.get("subtopic") or "", m.get("explanation") or "",
                         q_type, m.get("event_date"), pid,
                         _norm_dt(m.get("created_at"))),
                    )
                    inserted += 1
                except Exception:
                    skipped += 1
            supabase_mcq_ids   = {m["id"] for m in mcqs}
            supabase_cp_ids    = {p["mcq_id"] for p in progress}

            for p in progress:
                sb_reviewed    = _norm_dt(p.get("last_reviewed_at"))
                local          = local_cp.get(p["mcq_id"])
                local_reviewed = local.get("last_reviewed_at") if local else None

                # Prefer local when it was reviewed more recently (or when
                # Supabase has no reviewed_at yet, meaning the background sync
                # for a first-time Again press never completed).
                use_local = bool(
                    local and local_reviewed
                    and (not sb_reviewed or local_reviewed > sb_reviewed)
                )

                if use_local:
                    conn.execute(
                        """INSERT INTO card_progress
                           (id, mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count, review_tag)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"],
                         local["ease_factor"], local["interval_days"],
                         local["repetitions"], local["next_review_date"],
                         local["last_reviewed_at"],
                         local.get("again_count", 0), local.get("review_tag", "")),
                    )
                else:
                    sb_nrd    = _norm_dt(p.get("next_review_date")) or ""
                    local_nrd = (local.get("next_review_date") or "") if local else ""
                    final_nrd = (
                        local_nrd
                        if len(sb_nrd) == 10 and len(local_nrd) > 10
                        else sb_nrd
                    )
                    final_nrd = _snap_midnight(final_nrd)
                    conn.execute(
                        """INSERT INTO card_progress
                           (id, mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count, review_tag)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"], p["ease_factor"], p["interval_days"],
                         p["repetitions"], final_nrd,
                         _norm_dt(p.get("last_reviewed_at")), p.get("again_count", 0),
                         p.get("review_tag", "")),
                    )

            # Re-insert local rows for cards that exist in Supabase MCQs but
            # have no Supabase progress row yet (brand-new card pressed Again
            # before the background thread finished syncing to Supabase).
            for mcq_id, local in local_cp.items():
                if (mcq_id in supabase_mcq_ids
                        and mcq_id not in supabase_cp_ids
                        and local.get("last_reviewed_at")):
                    conn.execute(
                        """INSERT OR IGNORE INTO card_progress
                           (mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count, review_tag)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (mcq_id, local["ease_factor"], local["interval_days"],
                         local["repetitions"], local["next_review_date"],
                         local["last_reviewed_at"], local.get("again_count", 0),
                         local.get("review_tag", "")),
                    )

            for lg in logs:
                conn.execute(
                    """INSERT INTO review_logs (id, mcq_id, quality, was_correct, reviewed_at)
                       VALUES (?,?,?,?,?)""",
                    (lg["id"], lg["mcq_id"], lg["quality"], int(lg["was_correct"]),
                     _norm_dt(lg.get("reviewed_at"))),
                )

        self._sync_hidden_from_supabase()
        if backfilled_public_ids:
            def _push_backfilled_ids():
                for mcq_id, pid in backfilled_public_ids:
                    try:
                        self._sb.table("mcqs").update({"public_id": pid}).eq("id", mcq_id).execute()
                    except Exception:
                        pass  # Supabase may not have the public_id column yet — retried next sync
            threading.Thread(target=_push_backfilled_ids, daemon=True).start()
        return {"fetched": fetched, "inserted": inserted, "skipped": skipped}

    def _migrate_local_to_supabase(self) -> None:
        """Push existing local SQLite data up to Supabase (first-time migration)."""
        local_mcqs = self._local.list_mcqs()
        id_map: dict[int, int] = {}  # old local id → new supabase id

        for mcq in local_mcqs:
            row = self._sb.table("mcqs").insert({
                "question": mcq.question, "option_a": mcq.option_a, "option_b": mcq.option_b,
                "option_c": mcq.option_c, "option_d": mcq.option_d,
                "correct_answer": mcq.correct_answer, "subject": mcq.subject,
                "topic": mcq.topic, "subtopic": mcq.subtopic, "explanation": mcq.explanation,
                "question_type": mcq.question_type,
                "event_date": mcq.event_date.isoformat() if mcq.event_date else None,
                "public_id": mcq.public_id or _generate_public_id(),
            }).execute().data[0]
            id_map[mcq.id] = row["id"]

        with self._local._conn() as conn:
            # Remap local IDs to Supabase-assigned IDs
            for old_id, new_id in id_map.items():
                conn.execute("UPDATE mcqs SET id=? WHERE id=?", (new_id, old_id))
            progress_rows = conn.execute("SELECT * FROM card_progress").fetchall()
            log_rows = conn.execute("SELECT * FROM review_logs").fetchall()

        for p in progress_rows:
            new_mcq_id = id_map.get(p["mcq_id"], p["mcq_id"])
            self._sb.table("card_progress").insert({
                "mcq_id": new_mcq_id,
                "ease_factor": p["ease_factor"],
                "interval_days": p["interval_days"],
                "repetitions": p["repetitions"],
                "next_review_date": p["next_review_date"],
                "last_reviewed_at": p["last_reviewed_at"],
            }).execute()

        for lg in log_rows:
            new_mcq_id = id_map.get(lg["mcq_id"], lg["mcq_id"])
            self._sb.table("review_logs").insert({
                "mcq_id": new_mcq_id,
                "quality": lg["quality"],
                "was_correct": bool(lg["was_correct"]),
                "reviewed_at": lg["reviewed_at"],
            }).execute()

    # ── Reads → local SQLite ──────────────────────────────────────────────

    def get_mcq(self, mcq_id: int) -> Optional[MCQ]:
        return self._local.get_mcq(mcq_id)

    def get_mcq_by_public_id(self, public_id: str) -> Optional[MCQ]:
        return self._local.get_mcq_by_public_id(public_id)

    def list_mcqs(self, subject: str = "", topic: str = "", search: str = "",
                  limit: int = 0, offset: int = 0) -> list[MCQ]:
        return self._local.list_mcqs(subject, topic, search, limit, offset)

    def count_mcqs(self, subject: str = "", topic: str = "", search: str = "") -> int:
        return self._local.count_mcqs(subject, topic, search)

    def get_due_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        return self._local.get_due_mcqs(limit, subject, topic)

    def get_new_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        return self._local.get_new_mcqs(limit, subject, topic)

    def get_review_pool_mcqs(self, limit: Optional[int] = None, subject: str = "", topic: str = "") -> list[MCQ]:
        return self._local.get_review_pool_mcqs(limit, subject, topic)

    def get_subject_stats(self) -> list[dict]:
        return self._local.get_subject_stats()

    def get_topic_stats(self, subject: str) -> list[dict]:
        return self._local.get_topic_stats(subject)

    def get_recent_subject_activity(self, limit: int = 3) -> list[dict]:
        return self._local.get_recent_subject_activity(limit)

    def get_progress(self, mcq_id: int) -> Optional[CardProgress]:
        return self._local.get_progress(mcq_id)

    def get_stats(self) -> dict:
        return self._local.get_stats()

    def get_next_due_info(self) -> Optional[dict]:
        return self._local.get_next_due_info()

    def list_subjects(self) -> list[str]:
        return self._local.list_subjects()

    def list_topics(self, subject: str = "") -> list[str]:
        return self._local.list_topics(subject)

    def get_hidden_subjects(self) -> set:
        return self._local.get_hidden_subjects()

    def get_hidden_topics(self) -> set:
        return self._local.get_hidden_topics()

    def set_subject_hidden(self, subject: str, hidden: bool) -> None:
        self._local.set_subject_hidden(subject, hidden)
        try:
            self._sb.table("hidden_subjects").delete().eq("subject", subject).execute()
            if hidden:
                self._sb.table("hidden_subjects").insert({"subject": subject}).execute()
        except Exception:
            pass

    def set_topic_hidden(self, subject: str, topic: str, hidden: bool) -> None:
        self._local.set_topic_hidden(subject, topic, hidden)
        try:
            self._sb.table("hidden_topics").delete().eq("subject", subject).eq("topic", topic).execute()
            if hidden:
                self._sb.table("hidden_topics").insert({"subject": subject, "topic": topic}).execute()
        except Exception:
            pass

    # ── Writes → Supabase first, then mirror to local ─────────────────────

    def add_mcq(self, mcq: MCQ) -> MCQ:
        if not mcq.public_id:
            mcq.public_id = _generate_public_id()
        row = self._sb.table("mcqs").insert({
            "question": mcq.question, "option_a": mcq.option_a, "option_b": mcq.option_b,
            "option_c": mcq.option_c, "option_d": mcq.option_d,
            "correct_answer": mcq.correct_answer, "subject": mcq.subject,
            "topic": mcq.topic, "subtopic": mcq.subtopic, "explanation": mcq.explanation,
            "question_type": mcq.question_type,
            "event_date": mcq.event_date.isoformat() if mcq.event_date else None,
            "public_id": mcq.public_id,
        }).execute().data[0]
        mcq.id = row["id"]
        mcq.public_id = row.get("public_id") or mcq.public_id
        created = _norm_dt(row.get("created_at"))
        mcq.created_at = datetime.fromisoformat(created) if created else datetime.now()
        with self._local._conn() as conn:
            conn.execute(
                """INSERT INTO mcqs (id, question, option_a, option_b, option_c, option_d,
                   correct_answer, subject, topic, subtopic, explanation,
                   question_type, event_date, public_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mcq.id, mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.subtopic, mcq.explanation,
                 mcq.question_type,
                 mcq.event_date.isoformat() if mcq.event_date else None,
                 mcq.public_id, created),
            )
        return mcq

    def update_mcq(self, mcq: MCQ) -> MCQ:
        self._sb.table("mcqs").update({
            "question": mcq.question, "option_a": mcq.option_a, "option_b": mcq.option_b,
            "option_c": mcq.option_c, "option_d": mcq.option_d,
            "correct_answer": mcq.correct_answer, "subject": mcq.subject,
            "topic": mcq.topic, "subtopic": mcq.subtopic, "explanation": mcq.explanation,
            "question_type": mcq.question_type,
            "event_date": mcq.event_date.isoformat() if mcq.event_date else None,
        }).eq("id", mcq.id).execute()
        return self._local.update_mcq(mcq)

    def delete_mcq(self, mcq_id: int) -> None:
        self._sb.table("mcqs").delete().eq("id", mcq_id).execute()
        self._local.delete_mcq(mcq_id)

    def soft_sync(self) -> None:
        """Pull fresh card_progress from Supabase and merge with local SQLite.

        Lighter than a full _sync_from_supabase: does not wipe MCQs or
        review_logs, and still applies the local-wins merge so any unsynced
        Again presses are not overwritten.
        """
        try:
            progress = self._sb.table("card_progress").select("*").execute().data
        except Exception:
            return  # offline — keep whatever local data we have

        local_cp: dict[int, dict] = {}
        with self._local._conn() as snap:
            for row in snap.execute("SELECT * FROM card_progress").fetchall():
                local_cp[row["mcq_id"]] = {k: row[k] for k in row.keys()}

        with self._local._conn() as conn:
            for p in progress:
                sb_reviewed    = _norm_dt(p.get("last_reviewed_at"))
                local          = local_cp.get(p["mcq_id"])
                local_reviewed = local.get("last_reviewed_at") if local else None

                use_local = bool(
                    local and local_reviewed
                    and (not sb_reviewed or local_reviewed > sb_reviewed)
                )

                if not use_local:
                    sb_nrd    = _norm_dt(p.get("next_review_date")) or ""
                    local_nrd = (local.get("next_review_date") or "") if local else ""
                    # If Supabase only has a date (column type is 'date', not
                    # 'text'/'timestamp') keep the local full datetime so we
                    # don't lose the time component and make the card appear
                    # immediately due.
                    final_nrd = (
                        local_nrd
                        if len(sb_nrd) == 10 and len(local_nrd) > 10
                        else sb_nrd
                    )
                    final_nrd = _snap_midnight(final_nrd)
                    conn.execute(
                        """INSERT OR REPLACE INTO card_progress
                           (id, mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count, review_tag)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"], p["ease_factor"], p["interval_days"],
                         p["repetitions"], final_nrd,
                         _norm_dt(p.get("last_reviewed_at")), p.get("again_count", 0),
                         p.get("review_tag", "")),
                    )

    def save_progress(self, progress: CardProgress) -> CardProgress:
        # Write to local SQLite immediately so the UI can advance without waiting for network.
        self._local.save_progress(progress)

        # Snapshot values for the background thread (avoids capturing a mutable reference).
        data = {
            "mcq_id": progress.mcq_id,
            "ease_factor": progress.ease_factor,
            "interval_days": progress.interval_days,
            "repetitions": progress.repetitions,
            "next_review_date": progress.next_review_date.isoformat(),
            "last_reviewed_at": (
                progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None
            ),
            "again_count": progress.again_count,
            "review_tag": progress.review_tag,
        }
        mcq_id = progress.mcq_id

        def _sync():
            try:
                existing = (
                    self._sb.table("card_progress")
                    .select("id").eq("mcq_id", mcq_id).execute().data
                )
                if existing:
                    self._sb.table("card_progress").update(data).eq("mcq_id", mcq_id).execute()
                else:
                    self._sb.table("card_progress").insert(data).execute()
            except Exception:
                pass

        threading.Thread(target=_sync, daemon=False).start()
        return progress

    def delete_subject(self, subject: str) -> None:
        # Collect IDs before local delete so we can clean up Supabase relations.
        with self._local._conn() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM mcqs WHERE subject=?", (subject,)
            ).fetchall()]
        self._local.delete_subject(subject)
        if ids:
            def _sync():
                try:
                    self._sb.table("review_logs").delete().in_("mcq_id", ids).execute()
                    self._sb.table("card_progress").delete().in_("mcq_id", ids).execute()
                    self._sb.table("mcqs").delete().eq("subject", subject).execute()
                except Exception:
                    pass
            import threading
            threading.Thread(target=_sync, daemon=False).start()

    def delete_topic(self, subject: str, topic: str) -> None:
        with self._local._conn() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM mcqs WHERE subject=? AND topic=?", (subject, topic)
            ).fetchall()]
        self._local.delete_topic(subject, topic)
        if ids:
            def _sync():
                try:
                    self._sb.table("review_logs").delete().in_("mcq_id", ids).execute()
                    self._sb.table("card_progress").delete().in_("mcq_id", ids).execute()
                    self._sb.table("mcqs").delete().eq("subject", subject).eq("topic", topic).execute()
                except Exception:
                    pass
            import threading
            threading.Thread(target=_sync, daemon=False).start()

    def reset_schedule(self) -> None:
        self._local.reset_schedule()

    def add_review_log(self, log: ReviewLog) -> ReviewLog:
        # Write to local SQLite immediately.
        self._local.add_review_log(log)

        log_data = {
            "mcq_id": log.mcq_id,
            "quality": log.quality,
            "was_correct": log.was_correct,
            "reviewed_at": log.reviewed_at.isoformat(),
        }

        def _sync():
            try:
                self._sb.table("review_logs").insert(log_data).execute()
            except Exception:
                pass

        threading.Thread(target=_sync, daemon=False).start()
        return log
