"""Check account karma and filter subreddits accordingly."""

import asyncio
import re
from datetime import datetime, timezone

from src.log import get_logger

log = get_logger("karma")

_cached_karma: int | None = None
# Account age in days, scraped in the same profile pass as karma.
# None means "unknown" (callers fail closed where age is required).
_cached_age_days: int | None = None


async def get_account_karma(session) -> int:
    """Get the current account's comment karma.

    Caches the result for the duration of the cycle to avoid repeated checks.
    """
    global _cached_karma
    if _cached_karma is not None:
        return _cached_karma

    page = session.page
    try:
        # Navigate to the user profile
        username = await page.evaluate("""
            () => {
                // Try to get username from the page header
                const el = document.querySelector(
                    '[data-testid="username"], '
                    + 'a[href^="/user/"]'
                );
                if (el) {
                    const text = el.textContent.trim();
                    return text.replace('u/', '');
                }
                return '';
            }
        """)

        if not username:
            log.warning("Could not determine username from page")
            _cached_karma = 0
            return 0

        await page.goto(
            f"https://www.reddit.com/user/{username}/",
            wait_until="domcontentloaded",
        )
        await asyncio.sleep(2)

        # Extract karma from the profile page
        text = await page.evaluate("document.body.innerText")

        # Parse account age (cake-day) from the same page in one pass.
        _parse_and_cache_age(text)

        # Look for karma patterns like "1 karma" or "1,234 karma"
        karma_match = re.search(r"([\d,]+)\s+karma", text, re.IGNORECASE)
        if karma_match:
            karma = int(karma_match.group(1).replace(",", ""))
            log.info(f"Account karma: {karma}")
            _cached_karma = karma
            return karma

        log.warning("Could not parse karma from profile")
        _cached_karma = 0
        return 0

    except Exception as e:
        log.error(f"Failed to check karma: {e}")
        _cached_karma = 0
        return 0


def _parse_and_cache_age(profile_text: str) -> None:
    """Parse account age from profile text. Leaves cache None if unparseable.

    Reddit shows the cake-day in a few forms, e.g.:
      "Cake day: January 15, 2024"
      "Reddit age 2y" / "2y" next to the avatar
    We try the explicit date first (most reliable), then a relative "Ny/Nm".
    None on failure means "unknown" — callers fail closed where age matters.
    """
    global _cached_age_days

    # 1) Explicit cake day date: "Cake day: January 15, 2024"
    m = re.search(
        r"cake\s*day[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
        profile_text,
        re.IGNORECASE,
    )
    if m:
        for fmt in ("%B %d, %Y", "%B %d %Y"):
            try:
                created = datetime.strptime(m.group(1), fmt).replace(
                    tzinfo=timezone.utc
                )
                _cached_age_days = (datetime.now(timezone.utc) - created).days
                log.info(f"Account age: {_cached_age_days}d (cake day)")
                return
            except ValueError:
                continue

    # 2) Relative age, but ONLY when anchored to an age/cake label. Matching a
    #    bare "5 months" anywhere would catch a post timestamp ("5 months ago")
    #    and report a confidently-wrong age — which would let a too-young account
    #    pass the age gate. Anchoring keeps us fail-closed when unsure.
    m = re.search(
        r"(?:reddit\s*age|cake\s*day|account\s*age)[^\d]{0,20}(\d+)\s*(y|yr|year|mo|month)s?\b",
        profile_text,
        re.IGNORECASE,
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        _cached_age_days = n * 365 if unit.startswith("y") else n * 30
        log.info(f"Account age: ~{_cached_age_days}d (relative, anchored)")
        return

    log.warning("Could not parse account age; treating as unknown (fail closed)")
    _cached_age_days = None


async def get_account_age_days(session) -> int | None:
    """Get cached account age in days. None means unknown (fail closed).

    Relies on get_account_karma having run first in the cycle (same page pass).
    """
    return _cached_age_days


def reset_karma_cache() -> None:
    """Reset the karma + age cache (call at start of each cycle)."""
    global _cached_karma, _cached_age_days
    _cached_karma = None
    _cached_age_days = None


def can_post_to_subreddit(karma: int, min_karma: int) -> bool:
    """Check if the account has enough karma for a subreddit."""
    return karma >= min_karma
