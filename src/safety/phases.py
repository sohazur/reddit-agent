"""Account warming phases — gate behavior by accumulated karma.

A brand-new account that posts a promotional list gets filtered by Reddit (as
happened to ThinkTax3983's Dubai-agencies post at 5 karma). Real accounts earn
trust first. This maps karma to what the agent is allowed to do:

  PHASE 1  (< 50 karma)   warm up: comments only, no posts, no promo, join+upvote
  PHASE 2  (50-199)       establishing: + occasional soft/value posts, still no promo
  PHASE 3  (>= 200)       trusted: full strategy, tier-3 promo allowed (still rare)

Thresholds are configurable. The phase is computed fresh each cycle from the
account's current karma, so the account graduates itself as it earns karma.
"""

from dataclasses import dataclass

from src.log import get_logger

log = get_logger("phases")

# Karma thresholds for phase boundaries (configurable via Config).
PHASE_2_MIN_KARMA = 50
PHASE_3_MIN_KARMA = 200


@dataclass
class PhasePolicy:
    """What the account may do at its current karma level."""

    phase: int
    can_comment: bool
    can_post: bool          # create original posts (not comments)
    max_tier: int           # highest content tier allowed (1=value, 3=promo)
    label: str

    def allows_tier(self, tier: int) -> bool:
        return tier <= self.max_tier


def phase_for_karma(
    karma: int,
    phase2_min: int = PHASE_2_MIN_KARMA,
    phase3_min: int = PHASE_3_MIN_KARMA,
) -> PhasePolicy:
    """Compute the warming phase for a given karma level."""
    if karma >= phase3_min:
        return PhasePolicy(
            phase=3, can_comment=True, can_post=True, max_tier=3,
            label=f"trusted (>= {phase3_min} karma): full strategy, promo allowed",
        )
    if karma >= phase2_min:
        return PhasePolicy(
            phase=2, can_comment=True, can_post=True, max_tier=2,
            label=f"establishing ({phase2_min}-{phase3_min - 1} karma): soft posts, no promo",
        )
    return PhasePolicy(
        phase=1, can_comment=True, can_post=False, max_tier=1,
        label=f"warming (< {phase2_min} karma): comments only, no posts, no promo",
    )


def cap_tier_to_phase(desired_tier: int, policy: PhasePolicy) -> int:
    """Clamp a desired content tier to what the phase permits."""
    capped = min(desired_tier, policy.max_tier)
    if capped < desired_tier:
        log.info(
            f"Phase {policy.phase} caps tier {desired_tier} -> {capped} "
            f"({policy.label})"
        )
    return capped
