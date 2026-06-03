"""Tests for the global circuit breaker / kill switch."""

from unittest.mock import patch

import pytest

import src.safety.breaker as breaker


@pytest.fixture
def flag(tmp_path):
    path = tmp_path / "paused.flag"
    with patch.object(breaker, "PAUSED_FLAG", path):
        yield path


# ---------- trip / clear / state ----------

def test_starts_unpaused(flag):
    assert breaker.is_paused() is False


def test_trip_sets_paused_with_reason(flag):
    breaker.trip("shadowban detected")
    assert breaker.is_paused() is True
    state = breaker.get_state()
    assert state.paused is True
    assert state.reason == "shadowban detected"
    assert state.since  # timestamp present


def test_clear_resumes(flag):
    breaker.trip("x")
    assert breaker.clear() is True
    assert breaker.is_paused() is False


def test_clear_when_not_paused_returns_false(flag):
    assert breaker.clear() is False


# ---------- evaluate_feedback ----------

def test_shadowban_trips_immediately():
    reason = breaker.evaluate_feedback({"shadowbanned": 1}, {})
    assert reason is not None
    assert "shadowban" in reason


def test_high_removal_rate_trips_above_sample():
    reason = breaker.evaluate_feedback({"checked": 6, "removed": 4}, {})
    assert reason is not None
    assert "removal" in reason


def test_removal_rate_ignored_below_min_sample():
    # 2/2 removed = 100% but only 2 checked → below MIN_SAMPLE, don't trip.
    reason = breaker.evaluate_feedback({"checked": 2, "removed": 2}, {})
    assert reason is None


def test_high_deterministic_block_rate_trips():
    # 8 hard-rule blocks, 1 posted = 8/9, over threshold, above sample.
    reason = breaker.evaluate_feedback({}, {"deterministic_blocks": 8, "comments_posted": 1})
    assert reason is not None
    assert "block" in reason


def test_low_block_rate_does_not_trip():
    reason = breaker.evaluate_feedback({}, {"deterministic_blocks": 1, "comments_posted": 9})
    assert reason is None


def test_fuzzy_judge_blocks_do_not_trip_breaker():
    # A picky sub rejecting many comments on fit (fuzzy judge) is NOT a danger
    # signal — only deterministic hard-rule blocks should trip the breaker.
    reason = breaker.evaluate_feedback({}, {"compliance_blocks": 9, "comments_posted": 0})
    assert reason is None


def test_clean_cycle_does_not_trip():
    reason = breaker.evaluate_feedback(
        {"shadowbanned": 0, "checked": 10, "removed": 1},
        {"compliance_blocks": 0, "comments_posted": 10},
    )
    assert reason is None
