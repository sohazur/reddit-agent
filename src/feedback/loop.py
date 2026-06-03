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
                # Back off that sub: start a cooldown with the captured reason so
                # we don't keep posting into the same filter/mod removal.
                from src.safety.cooldown import start_cooldown
                reason = result.get("removal_reason") or "comment removed (reason unknown)"
                start_cooldown(comment["subreddit"], reason)
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
    """Check if a comment is invisible to logged-out users (shadowban indicator).

    Two-stage to avoid false positives on large threads (where a new low-karma
    comment is sorted to the bottom / collapsed and a text scan misses it even
    though it's perfectly public):

    1. In-thread incognito text match (fast, but fragile on big threads).
    2. If that misses, the AUTHORITATIVE check: the account's PUBLIC profile
       comments page viewed logged-out. A genuinely shadowbanned account shows
       ZERO comments there. If the profile shows comments (this one or others),
       it is NOT shadowbanned — the thread scan just missed it.
    """
    try:
        incognito_page = await session.new_incognito_page()
        try:
            visible = await check_comment_visible(
                incognito_page, thread_url, comment_text
            )
            if visible:
                return False  # found in-thread → definitely fine

            # Thread scan missed it — verify against the public profile before
            # crying shadowban. This is what prevents the big-thread false flag.
            profile_ok = await _profile_shows_comments(incognito_page, session)
            if profile_ok:
                log.info(
                    "Comment not found in-thread, but profile shows public "
                    "comments → NOT shadowbanned (likely buried in a big thread)"
                )
                return False

            log.warning(
                "Comment invisible in-thread AND profile shows no public "
                "comments — likely shadowban"
            )
            return True
        finally:
            await incognito_page.context.close()

    except Exception as e:
        log.error(f"Shadowban check error: {e}")
        return False  # Fail open — never false-accuse on error


async def _profile_shows_comments(incognito_page, session) -> bool:
    """Does the account's PUBLIC (logged-out) profile show any comments?

    Authoritative shadowban signal: a shadowbanned account's comments are
    invisible to logged-out users everywhere, including its profile. Returns
    True if the logged-out profile renders one or more comments.
    """
    try:
        username = (session.config.reddit_account.username or "").strip()
    except AttributeError:
        username = ""
    if not username:
        return True  # can't check → don't accuse

    await incognito_page.goto(
        f"https://www.reddit.com/user/{username}/comments/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(4)
    count = await incognito_page.evaluate("""
        () => {
            if (/blocked by network security|whoa there/i.test(document.body.innerText||''))
                return -1;  // bot-blocked, inconclusive
            return document.querySelectorAll(
                'shreddit-profile-comment, shreddit-comment, [data-testid="comment"]'
            ).length;
        }
    """)
    if count == -1:
        log.warning("Profile shadowban check inconclusive (bot-blocked) — fail open")
        return True  # inconclusive → don't accuse
    log.info(f"Public profile shows {count} comment(s) logged-out")
    return count > 0
