"""Tests for the three-tier content mix enforcement."""

from unittest.mock import patch

import pytest

from src.db import (
    get_connection,
    get_recent_tier_counts,
    init_db,
    record_comment,
    record_thread,
)
from src.intelligence.tiers import (
    allowed_tier,
    classify_desired_tier,
)


# ---------- pure window enforcement ----------

def test_empty_history_caps_at_tier_2():
    # Brand-new account should never start on a promo.
    d = allowed_tier(3, {1: 0, 2: 0, 3: 0})
    assert d.tier == 2


def test_tier_3_allowed_when_under_target():
    # 20 comments, 0 promos so far → a tier-3 is allowed (target 5%).
    counts = {1: 18, 2: 2, 3: 0}
    d = allowed_tier(3, counts, window=20)
    assert d.tier == 3


def test_tier_3_downgraded_when_full():
    # Already 1 promo in 20 (5%) → another would exceed target, downgrade.
    counts = {1: 17, 2: 2, 3: 1}
    d = allowed_tier(3, counts, window=20)
    assert d.tier < 3


def test_tier_3_not_leaked_on_small_window():
    # 9 comments, 0 promos. Posting a promo → 1/10 = 10%, double the 5% target.
    # Must downgrade rather than leak a burst of promo (the shill signal).
    d = allowed_tier(3, {1: 9})
    assert d.tier < 3


def test_tier_3_not_leaked_on_tiny_window():
    # 2 comments, posting a promo would be 33% — must not allow.
    d = allowed_tier(3, {1: 2})
    assert d.tier < 3


def test_tier_1_always_allowed():
    counts = {1: 20, 2: 0, 3: 0}
    d = allowed_tier(1, counts)
    assert d.tier == 1


def test_downgrades_to_one_when_higher_tiers_full():
    # tier 2 and 3 both over target → falls to 1.
    counts = {1: 5, 2: 14, 3: 1}
    d = allowed_tier(3, counts, window=20)
    assert d.tier == 1


# ---------- desired tier classification ----------

def test_classify_no_objective_is_tier_1():
    assert classify_desired_tier("", "", 10) == 1


def test_classify_high_relevance_is_tier_3():
    assert classify_desired_tier("promote X", "SEO", 9) == 3


def test_classify_mid_relevance_is_tier_2():
    assert classify_desired_tier("promote X", "SEO", 7) == 2


def test_classify_low_relevance_is_tier_1():
    assert classify_desired_tier("promote X", "SEO", 4) == 1


# ---------- DB tier persistence + window ----------

@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.db.DB_PATH", db_path):
        init_db(db_path)
        record_thread("t1", "SEO", "title", "http://x")
        yield db_path


def test_record_and_count_tiers(tmp_db):
    record_comment("c1", "t1", "SEO", "a", 8.0, tier=1)
    record_comment("c2", "t1", "SEO", "b", 8.0, tier=3)
    record_comment("c3", "t1", "SEO", "c", 8.0, tier=2)
    counts = get_recent_tier_counts(window=20)
    assert counts == {1: 1, 2: 1, 3: 1}


def test_default_tier_is_1(tmp_db):
    record_comment("c1", "t1", "SEO", "a", 8.0)
    assert get_recent_tier_counts()[1] == 1


def test_migration_adds_tier_column(tmp_path):
    # Simulate an old DB without the tier column, then re-init.
    db_path = tmp_path / "old.db"
    with patch("src.db.DB_PATH", db_path):
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """CREATE TABLE threads (id TEXT PRIMARY KEY, subreddit TEXT, title TEXT,
                 url TEXT, score INTEGER, comment_count INTEGER, relevance_score REAL,
                 first_seen_at TEXT, evaluated_at TEXT, status TEXT);
               CREATE TABLE comments (id TEXT PRIMARY KEY, thread_id TEXT, subreddit TEXT,
                 comment_text TEXT, quality_score REAL, posted_at TEXT, karma INTEGER,
                 last_checked_at TEXT, status TEXT, removal_reason TEXT);"""
        )
        conn.commit()
        conn.close()
        init_db(db_path)  # should ALTER TABLE to add tier
        with get_connection(db_path) as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(comments)").fetchall()}
        assert "tier" in cols
