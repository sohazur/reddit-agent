"""Cadence manager: posting quotas, cooldowns, and human-like timing.

Enforces safe posting rates to minimize detection:
- New accounts: 2-3 comments/day
- Established (3-4 months): 10-20/day safe
- Per-subreddit limits from subreddits.yaml
- Minimum 15-minute spacing, randomized
"""

import random
from datetime import datetime, timedelta

from src.config import Config, SubredditConfig
from src.db import get_connection, get_today_comment_count
from src.log import get_logger

log = get_logger("cadence")


class CadenceManager:
    """Manages posting rate and timing to stay under detection thresholds."""

    def __init__(self, config: Config):
        self.config = config
        self._last_post_time: datetime | None = None

    def can_post_today(self) -> bool:
        """Check if global daily quota allows more posts."""
        count = get_today_comment_count()
        allowed = count < self.config.max_comments_per_day
        if not allowed:
            log.info(f"Daily quota exhausted ({count}/{self.config.max_comments_per_day})")
        return allowed

    def can_post_to_subreddit(self, subreddit: SubredditConfig) -> bool:
        """Check if per-subreddit daily limit allows more posts."""
        count = get_today_comment_count(subreddit.name)
        allowed = count < subreddit.max_daily_comments
        if not allowed:
            log.info(
                f"r/{subreddit.name} quota exhausted "
                f"({count}/{subreddit.max_daily_comments})"
            )
        return allowed

    def can_post_now(self) -> bool:
        """Check if enough time has passed since the last post."""
        if self._last_post_time is None:
            # Check DB for the most recent post time
            self._last_post_time = self._get_last_post_time()

        if self._last_post_time is None:
            return True

        min_interval = timedelta(minutes=self.config.min_comment_interval_minutes)
        # Add randomization: 0.8x to 1.5x the minimum interval
        jitter = random.uniform(0.8, 1.5)
        actual_interval = min_interval * jitter

        elapsed = datetime.utcnow() - self._last_post_time
        if elapsed < actual_interval:
            remaining = (actual_interval - elapsed).total_seconds()
            log.info(f"Cooldown active: {remaining:.0f}s remaining")
            return False

        return True

    def record_post(self) -> None:
        """Record that a post was just made (updates internal timer)."""
        self._last_post_time = datetime.utcnow()

    def remaining_today(self) -> int:
        """How many more comments can be posted today."""
        count = get_today_comment_count()
        return max(0, self.config.max_comments_per_day - count)

    def remaining_for_subreddit(self, subreddit: SubredditConfig) -> int:
        """How many more comments can be posted to this subreddit today."""
        count = get_today_comment_count(subreddit.name)
        return max(0, subreddit.max_daily_comments - count)

    def get_wait_seconds(self) -> float:
        """Get the number of seconds to wait before the next post is allowed.

        Returns 0 if posting is allowed now.
        """
        if self._last_post_time is None:
            self._last_post_time = self._get_last_post_time()

        if self._last_post_time is None:
            return 0

        min_interval = timedelta(minutes=self.config.min_comment_interval_minutes)
        jitter = random.uniform(0.8, 1.5)
        actual_interval = min_interval * jitter

        elapsed = datetime.utcnow() - self._last_post_time
        if elapsed >= actual_interval:
            return 0

        return (actual_interval - elapsed).total_seconds()

    def _get_last_post_time(self) -> datetime | None:
        """Get the most recent post time from the DB."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(posted_at) FROM comments"
            ).fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return None
