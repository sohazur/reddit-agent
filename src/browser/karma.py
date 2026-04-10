"""Check account karma and filter subreddits accordingly."""

import asyncio
import re

from src.log import get_logger

log = get_logger("karma")

_cached_karma: int | None = None


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


def reset_karma_cache() -> None:
    """Reset the karma cache (call at start of each cycle)."""
    global _cached_karma
    _cached_karma = None


def can_post_to_subreddit(karma: int, min_karma: int) -> bool:
    """Check if the account has enough karma for a subreddit."""
    return karma >= min_karma
