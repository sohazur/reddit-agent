"""Tests for structured-learning exemplar selection.

The key correctness property: only comments that actually SURVIVED a feedback
check qualify as exemplars — never a fresh, unchecked karma=1 comment.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.db import get_connection, get_top_comments, init_db, record_comment, record_thread


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.db.DB_PATH", db_path):
        init_db(db_path)
        record_thread("t1", "SEO", "title", "http://x")
        yield db_path


def _add_comment(cid, karma, checked, status="posted", sub="SEO"):
    record_comment(cid, "t1", sub, f"comment {cid}", 8.0)
    with get_connection() as conn:
        conn.execute(
            "UPDATE comments SET karma = ?, status = ?, last_checked_at = ? WHERE id = ?",
            (karma, status, datetime.utcnow().isoformat() if checked else None, cid),
        )


def test_excludes_unchecked_comments(tmp_db):
    # High karma but never checked → must NOT be an exemplar.
    _add_comment("c1", karma=50, checked=False)
    assert get_top_comments("SEO", min_karma=5) == []


def test_includes_checked_surviving_comments(tmp_db):
    _add_comment("c1", karma=20, checked=True)
    _add_comment("c2", karma=15, checked=True)
    top = get_top_comments("SEO", min_karma=5)
    assert len(top) == 2
    assert top[0]["karma"] == 20  # ordered by karma desc


def test_excludes_removed_comments(tmp_db):
    _add_comment("c1", karma=30, checked=True, status="removed")
    assert get_top_comments("SEO", min_karma=5) == []


def test_respects_min_karma(tmp_db):
    _add_comment("c1", karma=3, checked=True)
    assert get_top_comments("SEO", min_karma=5) == []


def test_scoped_to_subreddit(tmp_db):
    _add_comment("c1", karma=20, checked=True, sub="SEO")
    assert get_top_comments("marketing", min_karma=5) == []
