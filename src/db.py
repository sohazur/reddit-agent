"""SQLite database for tracking threads, comments, and learnings."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.config import DB_PATH


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                relevance_score REAL,
                first_seen_at TEXT NOT NULL,
                evaluated_at TEXT,
                status TEXT DEFAULT 'new'  -- new, evaluated, commented, skipped
            );

            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES threads(id),
                subreddit TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                quality_score REAL,
                posted_at TEXT NOT NULL,
                karma INTEGER DEFAULT 1,
                last_checked_at TEXT,
                status TEXT DEFAULT 'posted',  -- posted, removed, shadowbanned, deleted
                removal_reason TEXT,
                FOREIGN KEY (thread_id) REFERENCES threads(id)
            );

            CREATE TABLE IF NOT EXISTS subreddit_intel (
                subreddit TEXT PRIMARY KEY,
                report_json TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                post_count_analyzed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cycle_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                threads_scanned INTEGER DEFAULT 0,
                threads_evaluated INTEGER DEFAULT 0,
                comments_posted INTEGER DEFAULT 0,
                comments_skipped INTEGER DEFAULT 0,
                errors TEXT,
                status TEXT DEFAULT 'running'  -- running, completed, failed
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                comments_posted INTEGER DEFAULT 0,
                comments_surviving INTEGER DEFAULT 0,
                comments_removed INTEGER DEFAULT 0,
                total_karma_gained INTEGER DEFAULT 0,
                shadowban_detected INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_threads_subreddit ON threads(subreddit);
            CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status);
            CREATE INDEX IF NOT EXISTS idx_comments_thread ON comments(thread_id);
            CREATE INDEX IF NOT EXISTS idx_comments_status ON comments(status);
            CREATE INDEX IF NOT EXISTS idx_comments_posted ON comments(posted_at);
        """)


@contextmanager
def get_connection(db_path: Path | None = None):
    """Get a database connection with WAL mode enabled."""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_thread(
    thread_id: str,
    subreddit: str,
    title: str,
    url: str,
    score: int = 0,
    comment_count: int = 0,
) -> None:
    """Record a discovered thread. Skips if already exists."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO threads
               (id, subreddit, title, url, score, comment_count, first_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (thread_id, subreddit, title, url, score, comment_count,
             datetime.utcnow().isoformat()),
        )


def update_thread_evaluation(thread_id: str, relevance_score: float, status: str) -> None:
    """Update a thread after evaluation."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE threads SET relevance_score = ?, status = ?, evaluated_at = ?
               WHERE id = ?""",
            (relevance_score, status, datetime.utcnow().isoformat(), thread_id),
        )


def record_comment(
    comment_id: str,
    thread_id: str,
    subreddit: str,
    comment_text: str,
    quality_score: float,
) -> None:
    """Record a posted comment."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO comments
               (id, thread_id, subreddit, comment_text, quality_score, posted_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (comment_id, thread_id, subreddit, comment_text, quality_score,
             datetime.utcnow().isoformat()),
        )


def get_comments_needing_check(hours_since_post: int = 4) -> list[dict]:
    """Get comments that need a feedback check."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, thread_id, subreddit, comment_text, posted_at, karma
               FROM comments
               WHERE status = 'posted'
               AND (last_checked_at IS NULL
                    OR julianday('now') - julianday(last_checked_at) > ?)
               ORDER BY posted_at ASC""",
            (hours_since_post / 24.0,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_comment_feedback(
    comment_id: str, karma: int, status: str, removal_reason: str | None = None
) -> None:
    """Update a comment with feedback data."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE comments
               SET karma = ?, status = ?, removal_reason = ?, last_checked_at = ?
               WHERE id = ?""",
            (karma, status, removal_reason, datetime.utcnow().isoformat(), comment_id),
        )


def get_today_comment_count(subreddit: str | None = None) -> int:
    """Get number of comments posted today, optionally filtered by subreddit."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_connection() as conn:
        if subreddit:
            row = conn.execute(
                """SELECT COUNT(*) FROM comments
                   WHERE posted_at >= ? AND subreddit = ?""",
                (today, subreddit),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM comments WHERE posted_at >= ?",
                (today,),
            ).fetchone()
        return row[0]


def has_commented_on_thread(thread_id: str) -> bool:
    """Check if we've already commented on a thread."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return row[0] > 0


def get_daily_summary() -> dict:
    """Get today's stats for the daily digest."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_connection() as conn:
        posted = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE posted_at >= ?", (today,)
        ).fetchone()[0]

        surviving = conn.execute(
            """SELECT COUNT(*) FROM comments
               WHERE posted_at >= ? AND status = 'posted'""",
            (today,),
        ).fetchone()[0]

        removed = conn.execute(
            """SELECT COUNT(*) FROM comments
               WHERE posted_at >= ? AND status = 'removed'""",
            (today,),
        ).fetchone()[0]

        karma = conn.execute(
            """SELECT COALESCE(SUM(karma - 1), 0) FROM comments
               WHERE posted_at >= ?""",
            (today,),
        ).fetchone()[0]

        best = conn.execute(
            """SELECT subreddit, comment_text, karma FROM comments
               WHERE posted_at >= ?
               ORDER BY karma DESC LIMIT 1""",
            (today,),
        ).fetchone()

        return {
            "date": today,
            "comments_posted": posted,
            "comments_surviving": surviving,
            "comments_removed": removed,
            "karma_gained": karma,
            "best_comment": dict(best) if best else None,
        }
