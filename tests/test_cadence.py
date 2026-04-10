"""Tests for the cadence manager."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cadence.manager import CadenceManager
from src.config import Config, RedditAccount, SubredditConfig
from src.db import init_db, record_comment


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    with patch("src.db.DB_PATH", db_path), \
         patch("src.cadence.manager.get_connection") as mock_conn, \
         patch("src.cadence.manager.get_today_comment_count") as mock_count:
        init_db(db_path)
        yield db_path, mock_count


@pytest.fixture
def config():
    return Config(
        reddit_account=RedditAccount("test_user", "test_pass"),
        anthropic_api_key="test-key",
        slack_webhook_url="",
        max_comments_per_day=5,
        min_comment_interval_minutes=20,
        quality_threshold=7,
        cycle_interval_hours=2,
    )


@pytest.fixture
def subreddit():
    return SubredditConfig(
        name="SEO",
        keywords=["AI search"],
        max_daily_comments=3,
        tone="Technical",
    )


class TestCadenceManager:
    def test_can_post_today_under_limit(self, config):
        """Should allow posting when under daily limit."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=2):
            cadence = CadenceManager(config)
            assert cadence.can_post_today() is True

    def test_can_post_today_at_limit(self, config):
        """Should block posting when at daily limit."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=5):
            cadence = CadenceManager(config)
            assert cadence.can_post_today() is False

    def test_can_post_to_subreddit_under_limit(self, config, subreddit):
        """Should allow posting to subreddit when under its limit."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=1):
            cadence = CadenceManager(config)
            assert cadence.can_post_to_subreddit(subreddit) is True

    def test_can_post_to_subreddit_at_limit(self, config, subreddit):
        """Should block posting to subreddit when at its limit."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=3):
            cadence = CadenceManager(config)
            assert cadence.can_post_to_subreddit(subreddit) is False

    def test_can_post_now_no_history(self, config):
        """Should allow posting when no prior posts exist."""
        with patch.object(CadenceManager, "_get_last_post_time", return_value=None):
            cadence = CadenceManager(config)
            assert cadence.can_post_now() is True

    def test_can_post_now_recent_post(self, config):
        """Should block posting when last post was too recent."""
        recent = datetime.utcnow() - timedelta(minutes=5)
        with patch.object(CadenceManager, "_get_last_post_time", return_value=recent):
            cadence = CadenceManager(config)
            assert cadence.can_post_now() is False

    def test_can_post_now_old_post(self, config):
        """Should allow posting when enough time has passed."""
        old = datetime.utcnow() - timedelta(hours=1)
        with patch.object(CadenceManager, "_get_last_post_time", return_value=old):
            cadence = CadenceManager(config)
            assert cadence.can_post_now() is True

    def test_remaining_today(self, config):
        """Should calculate remaining posts correctly."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=3):
            cadence = CadenceManager(config)
            assert cadence.remaining_today() == 2

    def test_remaining_today_exhausted(self, config):
        """Should return 0 when quota exhausted."""
        with patch("src.cadence.manager.get_today_comment_count", return_value=10):
            cadence = CadenceManager(config)
            assert cadence.remaining_today() == 0

    def test_record_post_updates_timer(self, config):
        """Should update internal timer when a post is recorded."""
        with patch.object(CadenceManager, "_get_last_post_time", return_value=None):
            cadence = CadenceManager(config)
            assert cadence._last_post_time is None
            cadence.record_post()
            assert cadence._last_post_time is not None
