"""Tests for the database layer."""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

import src.db as db_module
from src.db import (
    get_comments_needing_check,
    get_daily_summary,
    get_today_comment_count,
    has_commented_on_thread,
    init_db,
    record_comment,
    record_thread,
    update_comment_feedback,
    update_thread_evaluation,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Each test gets its own fresh database."""
    db_path = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = db_path
    init_db(db_path)
    yield db_path
    db_module.DB_PATH = original


def _uid() -> str:
    return uuid.uuid4().hex[:8]


class TestThreadOperations:
    def test_record_thread(self):
        """Should record a new thread."""
        tid = _uid()
        record_thread(tid, "SEO", "Test Thread", "https://reddit.com/r/SEO/abc", 10, 5)
        assert has_commented_on_thread(tid) is False

    def test_record_duplicate_thread(self):
        """Should silently skip duplicate threads."""
        tid = _uid()
        record_thread(tid, "SEO", "Test", "https://example.com", 10, 5)
        record_thread(tid, "SEO", "Test", "https://example.com", 10, 5)

    def test_update_thread_evaluation(self):
        """Should update thread evaluation status."""
        tid = _uid()
        record_thread(tid, "SEO", "Test", "https://example.com", 10, 5)
        update_thread_evaluation(tid, 8.5, "evaluated")


class TestCommentOperations:
    def test_record_comment(self):
        """Should record a posted comment."""
        tid, cid = _uid(), _uid()
        record_thread(tid, "SEO", "Test", "https://example.com", 10, 5)
        record_comment(cid, tid, "SEO", "Great point about AI", 8.0)
        assert has_commented_on_thread(tid) is True

    def test_today_comment_count(self):
        """Should count today's comments."""
        t1, t2, c1, c2 = _uid(), _uid(), _uid(), _uid()
        record_thread(t1, "SEO", "Test 1", "https://example.com/1", 1, 1)
        record_thread(t2, "SEO", "Test 2", "https://example.com/2", 1, 1)
        record_comment(c1, t1, "SEO", "Comment 1", 7.0)
        record_comment(c2, t2, "SEO", "Comment 2", 8.0)
        assert get_today_comment_count() == 2
        assert get_today_comment_count("SEO") == 2
        assert get_today_comment_count("other") == 0

    def test_update_comment_feedback(self):
        """Should update comment with feedback data."""
        tid, cid = _uid(), _uid()
        record_thread(tid, "SEO", "Test", "https://example.com", 1, 1)
        record_comment(cid, tid, "SEO", "Comment", 7.0)
        update_comment_feedback(cid, 15, "posted")

    def test_daily_summary(self):
        """Should generate accurate daily summary."""
        tid, cid = _uid(), _uid()
        record_thread(tid, "SEO", "Test", "https://example.com", 1, 1)
        record_comment(cid, tid, "SEO", "Comment 1", 8.0)

        summary = get_daily_summary()
        assert summary["comments_posted"] == 1
        assert summary["comments_surviving"] == 1
        assert summary["comments_removed"] == 0
