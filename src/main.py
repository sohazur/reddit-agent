"""Main orchestrator: runs one complete engagement cycle.

A cycle consists of:
1. Start browser session (login if needed)
2. For each target subreddit:
   a. Generate/refresh subreddit intelligence report (if stale)
   b. Scan for relevant threads
   c. Evaluate each thread's engagement opportunity
   d. For threads above threshold:
      - Generate a comment
      - Score comment quality
      - If quality passes: post via browser
      - Verify comment posted
3. Run feedback loop on past comments
4. Update learning memory
5. Send Slack notifications
6. Close browser

Usage:
    python -m src.main              # Run one cycle
    python -m src.main --feedback   # Run feedback loop only
    python -m src.main --digest     # Send daily digest only
"""

import argparse
import asyncio
import fcntl
import sys
from datetime import datetime
from pathlib import Path

from src.browser.session import RedditSession
from src.cadence.manager import CadenceManager
from src.config import Config, load_config, load_subreddits, DATA_DIR
from src.db import (
    get_daily_summary,
    init_db,
    record_comment,
    update_thread_evaluation,
)
from src.feedback.learning import update_learnings
from src.feedback.loop import run_feedback_loop
from src.intelligence.evaluator import evaluate_thread
from src.intelligence.generator import generate_comment
from src.intelligence.quality_scorer import score_comment
from src.intelligence.subreddit_intel import generate_intel_report
from src.integrations.slack import (
    send_alert,
    send_cycle_summary,
    send_daily_digest,
    send_notification,
)
from src.integrations.tracker import log_activity
from src.log import get_logger, setup_logging
from src.scanner.subreddit import read_thread_details, scan_subreddit

LOCKFILE = DATA_DIR / "agent.lock"

log = get_logger("main")


async def run_cycle(config: Config) -> dict:
    """Run one complete engagement cycle.

    Returns a summary dict with cycle stats.
    """
    cycle_id = setup_logging(config.log_level)
    log.info(f"Starting cycle {cycle_id}")

    results = {
        "cycle_id": cycle_id,
        "threads_scanned": 0,
        "threads_evaluated": 0,
        "comments_posted": 0,
        "comments_skipped": 0,
        "errors": 0,
    }

    cadence = CadenceManager(config)

    if not cadence.can_post_today():
        log.info("Daily quota exhausted, running feedback only")
        session = await RedditSession(config).start()
        try:
            feedback = await run_feedback_loop(config, session)
            update_learnings(feedback)
        finally:
            await session.close()
        return results

    session = await RedditSession(config).start()

    try:
        # Check session health
        if not await session.is_healthy():
            log.error("Session unhealthy, aborting cycle")
            send_alert(config, "WARNING", "Browser session unhealthy. Check credentials.")
            results["errors"] += 1
            return results

        # CRITICAL: Check inbox FIRST for bans, removals, mod messages
        from src.browser.inbox import check_inbox, apply_inbox_actions
        inbox_messages = await check_inbox(session)
        if inbox_messages:
            actions = apply_inbox_actions(inbox_messages, config)
            for action in actions:
                log.warning(f"Inbox action: {action}")
            # Reload subreddits config in case bans were applied
            config.subreddits = load_subreddits()

        # Check account karma to filter subreddits
        from src.browser.karma import get_account_karma, can_post_to_subreddit as karma_check, reset_karma_cache
        reset_karma_cache()
        account_karma = await get_account_karma(session)
        log.info(f"Account karma: {account_karma}")

        for subreddit in config.subreddits:
            if not cadence.can_post_today():
                log.info("Daily quota reached, stopping")
                break

            if not cadence.can_post_to_subreddit(subreddit):
                log.info(f"r/{subreddit.name} quota reached, skipping")
                continue

            # Skip subreddits that require more karma than we have
            if subreddit.min_karma > 0 and not karma_check(account_karma, subreddit.min_karma):
                log.info(
                    f"r/{subreddit.name} requires {subreddit.min_karma} karma "
                    f"(we have {account_karma}), skipping"
                )
                continue

            log.info(f"Processing r/{subreddit.name}")

            # Generate/refresh subreddit intelligence
            await generate_intel_report(config, session, subreddit)

            # Scan for threads
            threads = await scan_subreddit(session, subreddit, limit=10)
            results["threads_scanned"] += len(threads)

            for thread in threads:
                if not cadence.can_post_today():
                    break
                if not cadence.can_post_to_subreddit(subreddit):
                    break
                if not cadence.can_post_now():
                    wait_time = cadence.get_wait_seconds()
                    log.info(f"Waiting {wait_time:.0f}s for cooldown")
                    await asyncio.sleep(wait_time)

                # Use karma mode for subreddits with no min_karma requirement
                karma_mode = subreddit.min_karma == 0

                try:
                    await _process_thread(
                        config, session, subreddit, thread, cadence, results,
                        karma_mode=karma_mode,
                    )
                except Exception as e:
                    log.error(f"Error processing thread {thread.id}: {e}")
                    results["errors"] += 1
                    continue

        # Engagement: upvote, browse, reply to replies
        from src.browser.engage import upvote_posts, reply_to_replies, browse_subreddit

        if config.engage_upvote:
            log.info("Upvoting posts for natural activity")
            for sub in config.subreddits[:3]:
                if sub.min_karma <= account_karma:
                    try:
                        await upvote_posts(session, sub.name, count=2)
                    except Exception as e:
                        log.warning(f"Upvote failed in r/{sub.name}: {e}")

        if config.engage_reply:
            log.info("Checking for replies to our comments")
            try:
                await reply_to_replies(session, config)
            except Exception as e:
                log.warning(f"Reply check failed: {e}")

        if config.engage_browse:
            log.info("Browsing for natural activity")
            import random
            browse_subs = [s for s in config.subreddits if s.min_karma <= account_karma]
            if browse_subs:
                sub = random.choice(browse_subs)
                try:
                    await browse_subreddit(session, sub.name)
                except Exception as e:
                    log.warning(f"Browse failed: {e}")

        # Run feedback loop
        log.info("Running feedback loop")
        feedback = await run_feedback_loop(config, session)
        update_learnings(feedback)

        # Check for critical issues
        if feedback.get("shadowbanned", 0) > 0:
            send_alert(
                config,
                "CRITICAL",
                f"Shadowban detected on account u/{config.reddit_account.username}!",
            )

        if feedback.get("removed", 0) > feedback.get("checked", 1) * 0.5:
            send_alert(
                config,
                "WARNING",
                f"High removal rate: {feedback['removed']}/{feedback['checked']} comments removed",
            )

    except Exception as e:
        log.error(f"Cycle failed: {e}", exc_info=True)
        results["errors"] += 1
        send_alert(config, "CRITICAL", f"Cycle {cycle_id} failed: {e}")
    finally:
        await session.close()

    # Send cycle summary
    send_cycle_summary(config, results)

    log.info(
        f"Cycle {cycle_id} complete: {results['comments_posted']} posted, "
        f"{results['comments_skipped']} skipped, {results['errors']} errors"
    )
    return results


async def _process_thread(
    config: Config,
    session: RedditSession,
    subreddit,
    thread,
    cadence: CadenceManager,
    results: dict,
    karma_mode: bool = False,
) -> None:
    """Evaluate, generate, quality-check, and post a comment for one thread."""
    from src.browser.actions import post_comment as browser_post

    # Read full thread details
    thread_content = await read_thread_details(session, thread.url)
    comments_text = "\n".join(
        f"u/{c.get('author', 'anon')}: {c.get('body', '')}"
        for c in thread_content.get("comments", [])[:10]
    )

    # Evaluate thread (use karma-mode prompts for karma-building subs)
    score = await evaluate_thread(
        config=config,
        subreddit=subreddit,
        thread_title=thread.title,
        thread_body=thread_content.get("body", thread.body),
        thread_score=thread.score,
        thread_comment_count=thread.comment_count,
        thread_comments=comments_text,
        karma_mode=karma_mode,
    )
    results["threads_evaluated"] += 1
    update_thread_evaluation(thread.id, score.total, "evaluated")

    # Lower threshold for karma-building (5 instead of 7)
    threshold = 5 if karma_mode else config.quality_threshold
    if score.total < threshold:
        log.info(f"Thread {thread.id} scored {score.total}/10, skipping (threshold={threshold})")
        update_thread_evaluation(thread.id, score.total, "skipped")
        return

    # Generate comment (karma-mode = genuine, no brand agenda)
    comment_text = await generate_comment(
        config=config,
        subreddit=subreddit,
        thread_title=thread.title,
        thread_body=thread_content.get("body", thread.body),
        thread_comments=comments_text,
        karma_mode=karma_mode,
    )

    if not comment_text:
        log.warning(f"Failed to generate comment for thread {thread.id}")
        results["errors"] += 1
        return

    # Quality check
    quality = await score_comment(
        config=config,
        comment_text=comment_text,
        subreddit_name=subreddit.name,
        thread_title=thread.title,
    )

    if not quality.passed:
        log.info(f"Comment failed quality check: {quality.issues}")
        results["comments_skipped"] += 1

        # Try regenerating once
        log.info("Regenerating comment...")
        comment_text = await generate_comment(
            config=config,
            subreddit=subreddit,
            thread_title=thread.title,
            thread_body=thread_content.get("body", thread.body),
            thread_comments=comments_text,
            karma_mode=karma_mode,
        )

        if not comment_text:
            return

        quality = await score_comment(
            config=config,
            comment_text=comment_text,
            subreddit_name=subreddit.name,
            thread_title=thread.title,
        )

        if not quality.passed:
            log.info("Comment failed quality check twice, skipping thread")
            results["comments_skipped"] += 1
            return

    # Post the comment
    log.info(f"Posting comment to thread {thread.id}")
    post_result = await browser_post(session, thread.url, comment_text)

    if post_result["success"]:
        comment_id = post_result.get("comment_id", "unknown")
        record_comment(
            comment_id=comment_id,
            thread_id=thread.id,
            subreddit=subreddit.name,
            comment_text=comment_text,
            quality_score=quality.average,
        )
        update_thread_evaluation(thread.id, score.total, "commented")
        cadence.record_post()
        results["comments_posted"] += 1

        # Log to ai-marketing tracker
        log_activity(
            config=config,
            platform="reddit",
            action_type="comment",
            url=thread.url,
            content_summary=comment_text[:200],
            status="posted",
            engagement_notes=f"quality: {quality.average:.1f}, thread_score: {score.total}",
        )

        log.info(f"Comment posted! ID: {comment_id}, quality: {quality.average:.1f}")
    else:
        log.error(f"Failed to post comment: {post_result.get('error')}")
        results["errors"] += 1


def acquire_lock() -> bool:
    """Acquire a lockfile to prevent concurrent runs."""
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = open(LOCKFILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(datetime.utcnow().isoformat()))
        lock_fd.flush()
        return True
    except (IOError, OSError):
        log.warning("Another cycle is already running (lockfile held)")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Reddit engagement agent")
    parser.add_argument(
        "--feedback", action="store_true", help="Run feedback loop only"
    )
    parser.add_argument(
        "--digest", action="store_true", help="Send daily digest only"
    )
    args = parser.parse_args()

    config = load_config()
    init_db()

    if args.digest:
        summary = get_daily_summary()
        send_daily_digest(config, summary)
        return

    if not acquire_lock():
        sys.exit(0)

    if args.feedback:
        session = await RedditSession(config).start()
        try:
            feedback = await run_feedback_loop(config, session)
            update_learnings(feedback)
        finally:
            await session.close()
        return

    await run_cycle(config)


def cli():
    """Entry point for the `reddit-agent` command (installed via pip)."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
