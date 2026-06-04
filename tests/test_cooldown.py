"""Tests for per-subreddit removal cooldowns."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import src.safety.cooldown as cd


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "cooldowns.json"
    with patch.object(cd, "COOLDOWN_PATH", path):
        yield path


def test_no_cooldown_by_default(store):
    assert cd.is_on_cooldown("AskReddit") is False


def test_start_then_on_cooldown(store):
    cd.start_cooldown("AppDevelopersDubai", "removed by Reddit's filters", days=3)
    assert cd.is_on_cooldown("AppDevelopersDubai") is True
    assert cd.is_on_cooldown("appdevelopersdubai") is True  # case-insensitive


def test_records_reason(store):
    cd.start_cooldown("SEO", "no self-promotion allowed", days=2)
    actives = cd.active_cooldowns()
    assert len(actives) == 1
    assert actives[0].reason == "no self-promotion allowed"
    assert actives[0].subreddit == "seo"


def test_expired_cooldown_clears(store):
    cd.start_cooldown("SEO", "x", days=3)
    # Manually expire it.
    import json
    data = json.loads(store.read_text())
    data["seo"]["until"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.write_text(json.dumps(data))
    assert cd.is_on_cooldown("SEO") is False
    # And it's pruned.
    assert cd.active_cooldowns() == []


def test_other_subs_unaffected(store):
    cd.start_cooldown("SEO", "x", days=3)
    assert cd.is_on_cooldown("marketing") is False


def test_ban_cooldown_long_window(store):
    # A community ban is effectively permanent; main.py cools it down for a year.
    # Verify a 365-day cooldown holds the sub and survives near-term re-checks.
    cd.start_cooldown("AskReddit", "banned: you're currently banned", days=365)
    assert cd.is_on_cooldown("AskReddit") is True
    actives = cd.active_cooldowns()
    assert len(actives) == 1
    assert actives[0].reason.startswith("banned:")
    # Not yet expired at +30 days.
    until = datetime.fromisoformat(actives[0].until)
    assert until > datetime.now(timezone.utc) + timedelta(days=300)
