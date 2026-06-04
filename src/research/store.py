"""Persistence helpers for Research mode (opportunities, discovered subs, viral).

Thin wrappers over the shared SQLite connection. The schema itself lives in
src/db.init_db so migrations apply uniformly with the rest of the app.
"""

import hashlib
import json
from datetime import datetime

from src.db import get_connection
from src.log import get_logger

log = get_logger("research.store")


def opportunity_id(url: str) -> str:
    """Stable id for an opportunity, derived from its (normalized) URL.

    Using the URL — not the volatile thread id — means the same post is never
    recorded twice even if Reddit's DOM reports a different/empty id.
    """
    norm = (url or "").split("?")[0].rstrip("/").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def opportunity_exists(opp_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM opportunities WHERE id = ?", (opp_id,)
        ).fetchone()
        return row is not None


def record_opportunity(
    url: str,
    subreddit: str,
    thread_id: str,
    title: str,
    author: str,
    problem_summary: str,
    matched_services: list[str],
    suggested_angle: str,
    priority: int,
    confidence: float,
) -> str:
    """Insert a new opportunity. No-op (returns id) if already recorded."""
    opp_id = opportunity_id(url)
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO opportunities
               (id, subreddit, thread_id, url, title, author, problem_summary,
                matched_services, suggested_angle, priority, confidence,
                status, found_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
            (
                opp_id, subreddit, thread_id, url, title, author, problem_summary,
                json.dumps(matched_services or []), suggested_angle,
                int(priority), float(confidence), datetime.utcnow().isoformat(),
            ),
        )
    return opp_id


def get_opportunities(status: str | None = None, limit: int = 200) -> list[dict]:
    """Return opportunities (optionally filtered by status), best first."""
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                """SELECT * FROM opportunities WHERE status = ?
                   ORDER BY priority DESC, found_at DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM opportunities
                   ORDER BY priority DESC, found_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["matched_services"] = json.loads(d.get("matched_services") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["matched_services"] = []
        out.append(d)
    return out


def mark_opportunities_pushed(ids: list[str]) -> None:
    if not ids:
        return
    with get_connection() as conn:
        conn.executemany(
            "UPDATE opportunities SET status='pushed', pushed_at=? WHERE id=? AND status='new'",
            [(datetime.utcnow().isoformat(), i) for i in ids],
        )


def set_opportunity_status(opp_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE opportunities SET status=? WHERE id=?", (status, opp_id)
        )


def count_opportunities() -> dict:
    """Counts by status plus a grand total — used in digests/status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) c FROM opportunities GROUP BY status"
        ).fetchall()
    counts = {r["status"]: r["c"] for r in rows}
    counts["total"] = sum(counts.values())
    return counts


# ─── Discovered subreddits ─────────────────────────────────────────────────


def upsert_research_subreddit(
    name: str,
    discovered_via: str,
    relevance: int = 0,
    rationale: str = "",
    status: str = "candidate",
) -> None:
    """Add a discovered subreddit, or refresh its relevance if already known.

    Never downgrades an 'active'/'skip' status that a human (or scan) already
    set — discovery should not silently re-open a sub you decided to skip.
    """
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT status FROM research_subreddits WHERE name=?", (name,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE research_subreddits
                   SET relevance=MAX(relevance, ?), rationale=COALESCE(NULLIF(?,''), rationale)
                   WHERE name=?""",
                (int(relevance), rationale, name),
            )
        else:
            conn.execute(
                """INSERT INTO research_subreddits
                   (name, discovered_via, relevance, rationale, status, added_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, discovered_via, int(relevance), rationale, status,
                 datetime.utcnow().isoformat()),
            )


def get_research_subreddits(exclude_status: str = "skip", limit: int = 200) -> list[dict]:
    """Discovered subreddits worth scanning, most relevant first."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM research_subreddits WHERE status != ?
               ORDER BY relevance DESC, last_scanned_at IS NOT NULL, last_scanned_at ASC
               LIMIT ?""",
            (exclude_status, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def subreddit_known(name: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM research_subreddits WHERE name=?", (name,)
        ).fetchone() is not None


def mark_subreddit_scanned(name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE research_subreddits SET last_scanned_at=?, status=CASE status WHEN 'candidate' THEN 'active' ELSE status END WHERE name=?",
            (datetime.utcnow().isoformat(), name),
        )


def last_discovery_at() -> datetime | None:
    """Most recent time any subreddit was added via discovery (not seed)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(added_at) m FROM research_subreddits WHERE discovered_via != 'seed'"
        ).fetchone()
    if row and row["m"]:
        try:
            return datetime.fromisoformat(row["m"])
        except ValueError:
            return None
    return None


# ─── Viral observations (learning) ─────────────────────────────────────────


def record_viral_observation(
    thread_id: str, subreddit: str, title: str, url: str,
    score: int, comment_count: int,
) -> None:
    """Note a high-performing post we saw while scanning (for trend learning).

    Keeps the best-known score for a given post if seen again.
    """
    tid = thread_id or opportunity_id(url)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO viral_observations
               (id, subreddit, title, url, score, comment_count, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 score=MAX(score, excluded.score),
                 comment_count=MAX(comment_count, excluded.comment_count),
                 observed_at=excluded.observed_at""",
            (tid, subreddit, title, url, int(score), int(comment_count),
             datetime.utcnow().isoformat()),
        )


def get_top_viral(limit: int = 15, min_score: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM viral_observations WHERE score >= ?
               ORDER BY score DESC LIMIT ?""",
            (min_score, limit),
        ).fetchall()
    return [dict(r) for r in rows]
