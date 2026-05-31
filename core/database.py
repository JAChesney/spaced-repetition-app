"""
Repository layer. Swap SQLiteRepository for a Supabase/S3 implementation
by implementing the same AbstractRepository interface.
"""
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional
from .models import MCQ, CardProgress, ReviewLog


# ── Minimal Supabase REST client (replaces the 'supabase' pip package) ────────
# Uses httpx directly so it bundles cleanly on Android.

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

    def execute(self):
        import httpx
        with httpx.Client(headers=self._headers, timeout=30.0) as http:
            if self._method == "GET":
                resp = http.get(self._url, params=self._params)
            elif self._method == "POST":
                resp = http.post(self._url, json=self._body, params=self._params)
            elif self._method == "PATCH":
                resp = http.patch(self._url, json=self._body, params=self._params)
            else:  # DELETE
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
    """Thin wrapper around the Supabase REST API — no external package needed."""

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

# ──────────────────────────────────────────────────────────────────────────────


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
    def get_next_due_info(self) -> Optional[dict]: ...

    @abstractmethod
    def list_subjects(self) -> list[str]: ...

    @abstractmethod
    def list_topics(self, subject: str = "") -> list[str]: ...

    @abstractmethod
    def reset_schedule(self) -> None: ...

    def soft_sync(self) -> None:
        """Refresh card_progress from remote without wiping local data.
        No-op for local-only repos; overridden by CachedRepository."""


class SQLiteRepository(AbstractRepository):
    def __init__(self, db_path: str = "mcqs.db"):
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        return self._connection

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
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add columns introduced after the initial schema (safe to run on any DB version)."""
        existing_mcqs = {row[1] for row in conn.execute("PRAGMA table_info(mcqs)").fetchall()}
        mcq_migrations = [
            ("subtopic",      "ALTER TABLE mcqs ADD COLUMN subtopic TEXT NOT NULL DEFAULT ''"),
            ("question_type", "ALTER TABLE mcqs ADD COLUMN question_type TEXT NOT NULL DEFAULT 'STATIC'"),
            ("event_date",    "ALTER TABLE mcqs ADD COLUMN event_date TEXT"),
        ]
        for col, sql in mcq_migrations:
            if col not in existing_mcqs:
                conn.execute(sql)

        existing_cp = {row[1] for row in conn.execute("PRAGMA table_info(card_progress)").fetchall()}
        cp_migrations = [
            ("again_count", "ALTER TABLE card_progress ADD COLUMN again_count INTEGER NOT NULL DEFAULT 0"),
        ]
        for col, sql in cp_migrations:
            if col not in existing_cp:
                conn.execute(sql)

    # --- MCQ CRUD ---

    def add_mcq(self, mcq: MCQ) -> MCQ:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO mcqs (question, option_a, option_b, option_c, option_d,
                   correct_answer, subject, topic, subtopic, explanation,
                   question_type, event_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.subtopic, mcq.explanation,
                 mcq.question_type,
                 mcq.event_date.isoformat() if mcq.event_date else None),
            )
            mcq.id = cur.lastrowid
            mcq.created_at = datetime.now()
        return mcq

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
        today = datetime.now().isoformat()
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
        now = datetime.now().isoformat()
        sql = """SELECT m.* FROM mcqs m
                 LEFT JOIN card_progress cp ON cp.mcq_id = m.id
                 WHERE (cp.mcq_id IS NULL
                        OR (cp.repetitions = 0 AND cp.next_review_date <= ?))"""
        params: list = [now]
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
                       repetitions=?, next_review_date=?, last_reviewed_at=?, again_count=?
                       WHERE mcq_id=?""",
                    (progress.ease_factor, progress.interval_days, progress.repetitions,
                     progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None,
                     progress.again_count, progress.mcq_id),
                )
                progress.id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO card_progress
                       (mcq_id, ease_factor, interval_days, repetitions, next_review_date,
                        last_reviewed_at, again_count)
                       VALUES (?,?,?,?,?,?,?)""",
                    (progress.mcq_id, progress.ease_factor, progress.interval_days,
                     progress.repetitions, progress.next_review_date.isoformat(),
                     progress.last_reviewed_at.isoformat() if progress.last_reviewed_at else None,
                     progress.again_count),
                )
                progress.id = cur.lastrowid
        return progress

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
                   WHERE cp.mcq_id IS NULL
                         OR (cp.repetitions = 0 AND cp.next_review_date <= ?)""",
                (today,),
            ).fetchone()[0]
            reviewed_today = conn.execute(
                "SELECT COUNT(*) FROM review_logs WHERE date(reviewed_at)=date(?)", (today,)
            ).fetchone()[0]
        return {"total": total, "due": due, "new": new, "reviewed_today": reviewed_today}

    def get_next_due_info(self) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """SELECT MIN(next_review_date) as next_review_date, COUNT(*) as count
                   FROM card_progress
                   WHERE next_review_date > ?
                   GROUP BY strftime('%Y-%m-%dT%H', next_review_date)
                   ORDER BY MIN(next_review_date) ASC
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
        )


class CachedRepository(AbstractRepository):
    """Supabase is the source of truth; SQLite is a local read cache.

    Pulls all data from Supabase into SQLite on every startup.
    All reads go to SQLite (fast, works offline).
    All writes go to Supabase first, then are mirrored to SQLite.
    """

    def __init__(self, supabase_url: str, supabase_key: str, db_path: str = "mcqs.db"):
        self._sb = _SupabaseClient(supabase_url, supabase_key)
        self._db_path = db_path
        self._local = SQLiteRepository(db_path)
        self.last_sync_error: Optional[str] = None
        try:
            self._sync_from_supabase()
        except Exception as exc:
            self.last_sync_error = str(exc)

    def clear_local_cache_and_sync(self) -> None:
        """Delete the local SQLite file and re-sync from Supabase.

        Call this from a 'Force Sync' button in the UI to recover from a
        stale local cache without needing to go into Android Settings.
        """
        import os
        # Close existing connection so the file can be deleted
        if self._local._connection is not None:
            self._local._connection.close()
            self._local._connection = None
        try:
            os.remove(self._db_path)
        except FileNotFoundError:
            pass
        # Re-initialise the local DB (creates a fresh empty schema)
        self._local = SQLiteRepository(self._db_path)
        self.last_sync_error = None
        self._sync_from_supabase(force=True)

    # ── Sync ─────────────────────────────────────────────────────────────

    def _sync_from_supabase(self, force: bool = False) -> None:
        mcqs = self._sb.table("mcqs").select("*").execute().data
        progress = self._sb.table("card_progress").select("*").execute().data
        logs = self._sb.table("review_logs").select("*").execute().data

        # If Supabase is empty but local has data, push local up instead of wiping it
        if not mcqs and self._local.count_mcqs() > 0:
            self._migrate_local_to_supabase()
            return

        # Snapshot local card_progress before wiping so we can prefer it when
        # it is more recent than Supabase (handles daemon-thread sync not
        # completing before the app was closed).
        local_cp: dict[int, dict] = {}
        if not force:
            with self._local._conn() as snap:
                for row in snap.execute("SELECT * FROM card_progress").fetchall():
                    local_cp[row["mcq_id"]] = {k: row[k] for k in row.keys()}

        with self._local._conn() as conn:
            # Delete in child-first order to satisfy foreign key constraints
            conn.execute("DELETE FROM review_logs")
            conn.execute("DELETE FROM card_progress")
            conn.execute("DELETE FROM mcqs")
            for m in mcqs:
                conn.execute(
                    """INSERT INTO mcqs (id, question, option_a, option_b, option_c, option_d,
                       correct_answer, subject, topic, subtopic, explanation,
                       question_type, event_date, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (m["id"], m["question"], m["option_a"], m["option_b"], m["option_c"],
                     m["option_d"], m["correct_answer"], m.get("subject") or "",
                     m.get("topic") or "", m.get("subtopic") or "",
                     m.get("explanation") or "",
                     m.get("question_type") or "STATIC",
                     m.get("event_date"),
                     _norm_dt(m.get("created_at"))),
                )
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
                            next_review_date, last_reviewed_at, again_count)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"],
                         local["ease_factor"], local["interval_days"],
                         local["repetitions"], local["next_review_date"],
                         local["last_reviewed_at"],
                         local.get("again_count", 0)),
                    )
                else:
                    sb_nrd    = _norm_dt(p.get("next_review_date")) or ""
                    local_nrd = (local.get("next_review_date") or "") if local else ""
                    final_nrd = (
                        local_nrd
                        if len(sb_nrd) == 10 and len(local_nrd) > 10
                        else sb_nrd
                    )
                    conn.execute(
                        """INSERT INTO card_progress
                           (id, mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"], p["ease_factor"], p["interval_days"],
                         p["repetitions"], final_nrd,
                         _norm_dt(p.get("last_reviewed_at")), p.get("again_count", 0)),
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
                            next_review_date, last_reviewed_at, again_count)
                           VALUES (?,?,?,?,?,?,?)""",
                        (mcq_id, local["ease_factor"], local["interval_days"],
                         local["repetitions"], local["next_review_date"],
                         local["last_reviewed_at"], local.get("again_count", 0)),
                    )

            for lg in logs:
                conn.execute(
                    """INSERT INTO review_logs (id, mcq_id, quality, was_correct, reviewed_at)
                       VALUES (?,?,?,?,?)""",
                    (lg["id"], lg["mcq_id"], lg["quality"], int(lg["was_correct"]),
                     _norm_dt(lg.get("reviewed_at"))),
                )

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

    def list_mcqs(self, subject: str = "", topic: str = "", search: str = "",
                  limit: int = 0, offset: int = 0) -> list[MCQ]:
        return self._local.list_mcqs(subject, topic, search, limit, offset)

    def count_mcqs(self, subject: str = "", topic: str = "", search: str = "") -> int:
        return self._local.count_mcqs(subject, topic, search)

    def get_due_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]:
        return self._local.get_due_mcqs(limit, subject, topic)

    def get_new_mcqs(self, limit: int = 20, subject: str = "", topic: str = "") -> list[MCQ]:
        return self._local.get_new_mcqs(limit, subject, topic)

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

    # ── Writes → Supabase first, then mirror to local ─────────────────────

    def add_mcq(self, mcq: MCQ) -> MCQ:
        row = self._sb.table("mcqs").insert({
            "question": mcq.question, "option_a": mcq.option_a, "option_b": mcq.option_b,
            "option_c": mcq.option_c, "option_d": mcq.option_d,
            "correct_answer": mcq.correct_answer, "subject": mcq.subject,
            "topic": mcq.topic, "subtopic": mcq.subtopic, "explanation": mcq.explanation,
            "question_type": mcq.question_type,
            "event_date": mcq.event_date.isoformat() if mcq.event_date else None,
        }).execute().data[0]
        mcq.id = row["id"]
        created = _norm_dt(row.get("created_at"))
        mcq.created_at = datetime.fromisoformat(created) if created else datetime.now()
        with self._local._conn() as conn:
            conn.execute(
                """INSERT INTO mcqs (id, question, option_a, option_b, option_c, option_d,
                   correct_answer, subject, topic, subtopic, explanation,
                   question_type, event_date, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (mcq.id, mcq.question, mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d,
                 mcq.correct_answer, mcq.subject, mcq.topic, mcq.subtopic, mcq.explanation,
                 mcq.question_type,
                 mcq.event_date.isoformat() if mcq.event_date else None,
                 created),
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
                    conn.execute(
                        """INSERT OR REPLACE INTO card_progress
                           (id, mcq_id, ease_factor, interval_days, repetitions,
                            next_review_date, last_reviewed_at, again_count)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (p["id"], p["mcq_id"], p["ease_factor"], p["interval_days"],
                         p["repetitions"], final_nrd,
                         _norm_dt(p.get("last_reviewed_at")), p.get("again_count", 0)),
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
