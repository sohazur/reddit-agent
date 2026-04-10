"""Feedback loop: revisit past comments, track karma, detect issues."""

import asyncio
from datetime import datetime

from src.browser.actions import check_comment_visible, extract_thread_content
from src.config import Config
from src.db import (
    get_comments_needing_check,
    get_connection,
    update_comment_feedback,
)
from src.log import get_logger

log = get_logger("feedback")


async def run_feedback_loop(
    config: Config,
    session,  # RedditSession
) -> dict:
    """Check past comments for karma changes, removals, and shadowbans.

    Returns a summary dict with counts.
    """
    comments = get_comments_needing_check(hours_since_post=4)
    if not comments:
        log.info("No comments need feedback checking")
        return {"checked": 0, "removed": 0, "shadowbanned": 0}

    log.info(f"Checking feedback for {len(comments)} comments")

    results = {
        "checked": 0,
        "removed": 0,
        "shadowbanned": 0,
        "karma_changes": [],
    }

    for comment in comments:
        try:
            result = await _check_single_comment(config, session, comment)
            results["checked"] += 1

            if result["status"] == "removed":
                results["removed"] += 1
            elif result["status"] == "shadowbanned":
                results["shadowbanned"] += 1

            if result.get("karma_delta", 0) != 0:
                results["karma_changes"].append({
                    "comment_id": comment["id"],
                    "subreddit": comment["subreddit"],
                    "old_karma": comment["karma"],
                    "new_karma": result["new_karma"],
                    "delta": result["karma_delta"],
                })

        except Exception as e:
            log.error(f"Error checking comment {comment['id']}: {e}")
            continue

    log.info(
        f"Feedback complete: {results['checked']} checked, "
        f"{results['removed']} removed, {results['shadowbanned']} shadowbanned"
    )
    return results


async def _check_single_comment(
    config: Config,
    session,  # RedditSession
    comment: dict,
) -> dict:
    """Check a single comment's status and karma."""
    thread_id = comment["thread_id"]

    # Get the thread URL from DB
    with get_connection() as conn:
        thread = conn.execute(
            "SELECT url FROM threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if not thread:
            return {"status": "unknown", "new_karma": 0, "karma_delta": 0}
        thread_url = thread[0]

    # Navigate to the thread and find our comment
    page = session.page
    thread_content = await extract_thread_content(session, thread_url, max_comments=30)

    # Search for our comment in the thread
    comment_snippet = comment["comment_text"][:50]
    found = False
    new_karma = comment["karma"]

    for c in thread_content.get("comments", []):
        if comment_snippet in c.get("body", ""):
            found = True
            new_karma = c.get("score", 0)
            break

    if not found:
        # Comment not found in thread — might be removed or shadowbanned
        # Do shadowban check
        is_shadowbanned = await _check_shadowban(
            session, thread_url, comment["comment_text"]
        )

        if is_shadowbanned:
            status = "shadowbanned"
            log.warning(f"Comment {comment['id']} appears shadowbanned!")
        else:
            status = "removed"
            log.info(f"Comment {comment['id']} was removed")

        update_comment_feedback(comment["id"], 0, status, "not_visible")
        return {"status": status, "new_karma": 0, "karma_delta": -comment["karma"]}

    # Comment still visible — update karma
    karma_delta = new_karma - comment["karma"]
    update_comment_feedback(comment["id"], new_karma, "posted")

    if karma_delta != 0:
        log.info(f"Comment {comment['id']}: karma {comment['karma']} → {new_karma} ({karma_delta:+d})")

    return {"status": "posted", "new_karma": new_karma, "karma_delta": karma_delta}


async def _check_shadowban(
    session,  # RedditSession
    thread_url: str,
    comment_text: str,
) -> bool:
    """Check if a comment is invisible to logged-out users (shadowban indicator)."""
    try:
        incognito_page = await session.new_incognito_page()
        visible = await check_comment_visible(
            incognito_page, thread_url, comment_text
        )
        await incognito_page.context.close()

        if not visible:
            log.warning("Comment not visible in incognito — possible shadowban")
            return True
        return False

    except Exception as e:
        log.error(f"Shadowban check error: {e}")
        return False  # Assume not shadowbanned on error
