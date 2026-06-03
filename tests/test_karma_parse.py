"""Tests for karma + account-age parsing across Reddit profile layouts.

Pure-function tests (no browser). The live dry-run showed the old regex read
ThinkTax3983's '5 Karma' / '3 m Reddit Age' as 0 / unknown.
"""

import src.browser.karma as karma
from src.browser.karma import _parse_karma


def setup_function():
    karma.reset_karma_cache()


# ---------- karma across layouts ----------

def test_karma_inline_lowercase():
    assert _parse_karma("5 karma") == 5


def test_karma_number_then_label_modern():
    # Modern profile: "5" on one line, "Karma" on the next.
    assert _parse_karma("ThinkTax3983\n5\nKarma\n24\nContributions") == 5


def test_karma_label_then_number():
    assert _parse_karma("Karma\n1,234") == 1234


def test_karma_with_commas():
    assert _parse_karma("12,345 karma") == 12345


def test_karma_none_when_absent():
    assert _parse_karma("no numbers about points here") is None


# ---------- account age ----------

def test_age_modern_number_before_label():
    # The exact ThinkTax3983 layout: "3 m" then "Reddit Age".
    karma._parse_and_cache_age("0 followers\n5\nKarma\n3 m\nReddit Age\n0\nGold earned")
    assert karma._cached_age_days == 90  # 3 months * 30


def test_age_years_single_letter():
    karma._parse_and_cache_age("2 y\nReddit Age")
    assert karma._cached_age_days == 730


def test_age_label_before_number():
    karma._parse_and_cache_age("Reddit age 2y")
    assert karma._cached_age_days == 730


def test_age_explicit_cake_day_date():
    karma._parse_and_cache_age("Cake day: January 15, 2024")
    assert karma._cached_age_days is not None and karma._cached_age_days > 300


def test_age_unknown_stays_none_fail_closed():
    # A bare post timestamp must NOT be read as account age.
    karma._parse_and_cache_age("top comment posted 5 months ago by someone")
    assert karma._cached_age_days is None
