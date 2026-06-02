"""Tests for the deterministic compliance gate.

The deterministic gate is the safety floor. These tests verify it FAILS CLOSED
on every uncertain decision and never lets a banned post through.
"""

import pytest

from src.config import SubredditConfig
from src.intelligence.compliance import (
    GateResult,
    SubredditPolicy,
    contains_link,
    deterministic_gate,
    extract_policy,
    strip_links,
)


# ---------- link detection ----------

@pytest.mark.parametrize("text", [
    "check this https://example.com out",
    "go to www.example.com",
    "see example.com for details",
    "visit example dot com",
    "try example[.]com now",
    "my site is foo.io seriously",
])
def test_contains_link_detects_urls_and_obfuscations(text):
    assert contains_link(text) is True


@pytest.mark.parametrize("text", [
    "this is a normal comment with no links",
    "i think that's a good idea honestly",
    "yeah we hit that too, annoying",
])
def test_contains_link_false_on_clean_text(text):
    assert contains_link(text) is False


def test_strip_links_removes_url_keeps_text():
    out = strip_links("great tool, see https://example.com it works")
    assert "example.com" not in out
    assert "great tool" in out


# ---------- karma gate ----------

def test_blocks_when_karma_below_min():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, min_karma=50)
    res = deterministic_gate("a fine comment", policy, account_karma=10, account_age_days=999)
    assert res.blocked
    assert any("karma" in r for r in res.reasons)


def test_allows_when_karma_meets_min():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, min_karma=50)
    res = deterministic_gate("a fine comment", policy, account_karma=60, account_age_days=999)
    assert res.allowed


# ---------- account age gate (fail closed) ----------

def test_blocks_when_age_unknown_but_required():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, min_account_age_days=30)
    res = deterministic_gate("a fine comment", policy, account_karma=999, account_age_days=None)
    assert res.blocked
    assert any("age unknown" in r for r in res.reasons)


def test_blocks_when_age_too_young():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, min_account_age_days=30)
    res = deterministic_gate("a fine comment", policy, account_karma=999, account_age_days=5)
    assert res.blocked


def test_allows_when_age_unknown_and_not_required():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, min_account_age_days=0)
    res = deterministic_gate("a fine comment", policy, account_karma=999, account_age_days=None)
    assert res.allowed


# ---------- self-promotion ----------

def test_blocks_self_promotion():
    policy = SubredditPolicy(no_links=False, no_self_promotion=True)
    res = deterministic_gate("honestly just DM me and I'll help", policy, 999, 999)
    assert res.blocked
    assert any("self-promotion" in r for r in res.reasons)


def test_allows_self_promo_when_tolerated():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False)
    res = deterministic_gate("i built a thing for this", policy, 999, 999)
    assert res.allowed


# ---------- banned phrases ----------

def test_blocks_banned_phrase():
    policy = SubredditPolicy(no_links=False, no_self_promotion=False, banned_phrases=["upvote me"])
    res = deterministic_gate("please upvote me thanks", policy, 999, 999)
    assert res.blocked


# ---------- links ----------

def test_strips_links_when_banned_and_allows_rest():
    policy = SubredditPolicy(no_links=True, no_self_promotion=False)
    res = deterministic_gate("good point, see https://example.com for more", policy, 999, 999)
    assert res.allowed
    assert res.rewritten_text is not None
    assert "example.com" not in res.rewritten_text


def test_blocks_link_only_comment():
    policy = SubredditPolicy(no_links=True, no_self_promotion=False)
    res = deterministic_gate("https://example.com", policy, 999, 999)
    assert res.blocked


def test_blocks_link_when_strip_disabled():
    policy = SubredditPolicy(no_links=True, no_self_promotion=False)
    res = deterministic_gate(
        "see https://example.com", policy, 999, 999, strip_links_if_banned=False
    )
    assert res.blocked


# ---------- empty ----------

def test_blocks_empty_comment():
    res = deterministic_gate("   ", SubredditPolicy(), 999, 999)
    assert res.blocked


# ---------- policy extraction (fail closed) ----------

def _sub(**kw):
    base = dict(name="x", keywords=[], max_daily_comments=2, tone="")
    base.update(kw)
    return SubredditConfig(**base)


def test_extract_policy_strict_default_on_empty_report():
    policy = extract_policy("", _sub())
    assert policy.no_links is True
    assert policy.no_self_promotion is True


def test_extract_policy_strict_default_on_bad_json():
    policy = extract_policy("not json{", _sub())
    assert policy.no_links is True
    assert policy.no_self_promotion is True


def test_extract_policy_respects_config_overrides():
    policy = extract_policy("", _sub(min_karma=50, min_account_age_days=30))
    assert policy.min_karma == 50
    assert policy.min_account_age_days == 30


def test_extract_policy_high_tolerance_allows_links_and_promo():
    report = '{"self_promotion_tolerance": "high", "avoid": []}'
    policy = extract_policy(report, _sub())
    assert policy.no_self_promotion is False
    assert policy.no_links is False


def test_extract_policy_avoid_links_keeps_no_links():
    report = '{"self_promotion_tolerance": "high", "avoid": ["no external links"]}'
    policy = extract_policy(report, _sub())
    assert policy.no_links is True
