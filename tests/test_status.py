"""Tests for the agent-facing status snapshot."""

from unittest.mock import patch

import pytest

import src.status as status_mod
import src.safety.breaker as breaker
from src.config import Config, RedditAccount


def _config(**kw):
    base = dict(
        reddit_account=RedditAccount("u", "p"),
        anthropic_api_key="k",
        slack_webhook_url="",
        max_comments_per_day=5,
        min_comment_interval_minutes=20,
        quality_threshold=7,
        cycle_interval_hours=2,
    )
    base.update(kw)
    return Config(**base)


@pytest.fixture
def env(tmp_path):
    """Isolate the lockfile and pause flag, and stub the comment count."""
    lock = tmp_path / "agent.lock"
    flag = tmp_path / "paused.flag"
    with patch.object(status_mod, "LOCKFILE", lock), \
         patch.object(breaker, "PAUSED_FLAG", flag), \
         patch("src.status.get_today_comment_count", return_value=0):
        yield lock, flag


def test_should_run_when_never_run(env):
    s = status_mod.build_status(_config())
    assert s["last_run"] is None
    assert s["should_run"] is True
    assert s["alerts"] == []


def test_paused_blocks_should_run(env):
    breaker.trip("shadowban detected")
    s = status_mod.build_status(_config())
    assert s["paused"] is True
    assert s["should_run"] is False
    assert any("PAUSED" in a for a in s["alerts"])


def test_quota_exhausted_blocks_should_run(env):
    with patch("src.status.get_today_comment_count", return_value=5):
        s = status_mod.build_status(_config(max_comments_per_day=5))
    assert s["today"]["quota_left"] == 0
    assert s["should_run"] is False
    assert any("quota" in a for a in s["alerts"])


def test_recent_run_blocks_until_interval(env):
    lock, _ = env
    lock.write_text("now")  # fresh mtime → hours_since ~0
    s = status_mod.build_status(_config(cycle_interval_hours=2))
    assert s["hours_since"] is not None
    assert s["should_run"] is False  # not enough time elapsed


def test_dry_run_surfaced(env):
    s = status_mod.build_status(_config(dry_run=True))
    assert s["dry_run"] is True
