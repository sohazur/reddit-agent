"""Three-tier content mix for building topical authority.

The account should read as a real expert who occasionally has a product, not a
shill. Each comment is one of three tiers:

  TIER 1  pure value / topic content, no agenda      (~70%)
  TIER 2  topic content with soft brand relevance     (~25%)
  TIER 3  direct brand/product mention                (~5%, rare)

Enforcement is over a ROLLING WINDOW of recent comments (not per cycle), so the
ratio is meaningful even at 2-20 comments/day. Before generating, we pick the
highest tier the window still permits. If tier 3 (or 2) is "full" for the
window, the opportunity is downgraded toward tier 1 rather than skipped — the
agent still contributes value, just without the promo.
"""

from dataclasses import dataclass

from src.log import get_logger

log = get_logger("tiers")

# Default target shares per tier. Configurable via Config.tier_ratio.
DEFAULT_TIER_RATIO = {1: 0.70, 2: 0.25, 3: 0.05}


@dataclass
class TierDecision:
    tier: int
    reason: str


def allowed_tier(
    desired_tier: int,
    recent_counts: dict[int, int],
    window: int = 20,
    ratio: dict[int, float] | None = None,
) -> TierDecision:
    """Pick the highest tier <= desired that the rolling window still permits.

    A tier is "full" when its share of the window already meets or exceeds its
    target. We downgrade (3 -> 2 -> 1) until we find an allowed tier. Tier 1 is
    always allowed (pure value never hurts).
    """
    ratio = ratio or DEFAULT_TIER_RATIO
    total = sum(recent_counts.get(t, 0) for t in (1, 2, 3))

    # Empty history: honor the desired tier (nothing to balance against yet),
    # but never start a brand-new account on a promo.
    if total == 0:
        tier = min(desired_tier, 2)
        return TierDecision(tier=tier, reason="no history; honoring desired (capped at 2)")

    for tier in range(desired_tier, 1, -1):
        target = ratio.get(tier, 0.0)
        # Gate on the share AFTER posting one more, so a single post can't
        # overshoot a small window (e.g. tier 3 hitting 33% on a 2-comment
        # history). No slack: a rare tier genuinely waits until enough value
        # history exists to "afford" it. Tier 1 is always allowed (loop floor),
        # so there is no deadlock.
        projected_share = (recent_counts.get(tier, 0) + 1) / (total + 1)
        if projected_share <= target + 1e-9:
            return TierDecision(
                tier=tier,
                reason=f"tier {tier} within target (projected {projected_share:.0%} <= {target:.0%})",
            )
        log.info(f"Tier {tier} full (projected {projected_share:.0%} > {target:.0%}), downgrading")

    return TierDecision(tier=1, reason="downgraded to tier 1 (higher tiers full)")


def classify_desired_tier(objective: str, domain: str, relevance_score: float) -> int:
    """Heuristic desired tier from how brand-relevant the opportunity is.

    Pure value (low brand relevance) -> tier 1. Strong brand fit -> tier 3.
    The rolling-window enforcer then caps this to keep promo rare. relevance is
    the evaluator's 0-10 thread score.
    """
    if not objective and not domain:
        return 1
    if relevance_score >= 9:
        return 3
    if relevance_score >= 7:
        return 2
    return 1
