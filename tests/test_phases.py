"""Tests for account-warming phases."""

from src.safety.phases import cap_tier_to_phase, phase_for_karma


def test_phase1_low_karma_comments_only_no_promo():
    p = phase_for_karma(5)  # the ThinkTax3983 case
    assert p.phase == 1
    assert p.can_comment is True
    assert p.can_post is False
    assert p.max_tier == 1
    assert p.allows_tier(1) is True
    assert p.allows_tier(2) is False
    assert p.allows_tier(3) is False


def test_phase2_soft_posts_no_promo():
    p = phase_for_karma(120)
    assert p.phase == 2
    assert p.can_post is True
    assert p.max_tier == 2
    assert p.allows_tier(2) is True
    assert p.allows_tier(3) is False


def test_phase3_full_strategy():
    p = phase_for_karma(500)
    assert p.phase == 3
    assert p.max_tier == 3
    assert p.allows_tier(3) is True


def test_phase_boundaries_inclusive():
    assert phase_for_karma(49).phase == 1
    assert phase_for_karma(50).phase == 2
    assert phase_for_karma(199).phase == 2
    assert phase_for_karma(200).phase == 3


def test_custom_thresholds():
    p = phase_for_karma(30, phase2_min=20, phase3_min=100)
    assert p.phase == 2


def test_cap_tier_downgrades_to_phase_max():
    p1 = phase_for_karma(5)
    assert cap_tier_to_phase(3, p1) == 1  # promo capped to value at low karma


def test_cap_tier_noop_when_within_phase():
    p3 = phase_for_karma(500)
    assert cap_tier_to_phase(3, p3) == 3


def test_dubai_post_would_be_blocked_at_5_karma():
    # The screenshot: a promotional (tier 3) list post from a 5-karma account.
    # Phase 1 caps tier to 1 → no promo. This is the guardrail.
    p = phase_for_karma(5)
    assert cap_tier_to_phase(3, p) == 1
    assert p.can_post is False
