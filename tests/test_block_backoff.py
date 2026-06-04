"""Tests for the network-block adaptive backoff."""

from datetime import datetime, timedelta, timezone

import pytest

import src.safety.block_backoff as bb


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "block_backoff.json"
    monkeypatch.setattr(bb, "BACKOFF_PATH", path)
    yield path


def test_none_by_default(store):
    assert bb.seconds_remaining() == 0
    assert bb.is_backing_off() is False


def test_records_and_escalates(store):
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    first = bb.record_block(now)
    second = bb.record_block(now)
    third = bb.record_block(now)
    fourth = bb.record_block(now)
    assert first == 300            # 5 min
    assert second == 1200          # 20 min
    assert third == 3600           # 60 min
    assert fourth == 3600          # clamped at the last step


def test_backing_off_then_expires(store):
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    bb.record_block(now)  # 5 min
    # 1 minute later — still backing off.
    assert bb.is_backing_off(now + timedelta(minutes=1)) is True
    assert bb.seconds_remaining(now + timedelta(minutes=1)) == 240
    # 6 minutes later — expired.
    assert bb.is_backing_off(now + timedelta(minutes=6)) is False
    assert bb.seconds_remaining(now + timedelta(minutes=6)) == 0


def test_clear_resets_streak(store):
    now = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
    bb.record_block(now)
    bb.record_block(now)
    bb.clear()
    assert bb.seconds_remaining() == 0
    # After a clear, the streak restarts at the first step.
    assert bb.record_block(now) == 300
