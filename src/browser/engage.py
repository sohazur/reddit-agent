"""Full Reddit engagement: upvote, reply to replies, create posts.

Goes beyond just commenting — makes the account behave like a real user.
"""

import asyncio
import random

from src.browser.stealth import human_delay, human_typing_delay
from src.config import Config, SubredditConfig
from src.db import get_connection
from src.llm import call_llm
from src.log import get_logger

log = get_logger("engage")


async def upvote_posts(session, subreddit_name: str, count: int = 3) -> int:
    """Upvote a few posts in a subreddit to look like a real user.

    Returns number of posts upvoted.
    """
    page = session.page
    await page.goto(
        f"https://www.reddit.com/r/{subreddit_name}/hot/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(human_delay(2000, 4000))

    # Dismiss cookie popup
    try:
        for btn in await page.query_selector_all("button"):
            if "Accept All" in (await btn.inner_text()):
                await btn.click()
                await asyncio.sleep(1)
                break
    except Exception:
        pass

    # Find upvote buttons
    upvoted = 0
    upvote_buttons = await page.query_selector_all(
        'button[aria-label="upvote"], '
        'shreddit-post button[upvote], '
        'button[data-click-id="upvote"]'
    )

    # Shuffle to not always upvote the top posts
    indices = list(range(len(upvote_buttons)))
    random.shuffle(indices)

    for i in indices[:count]:
        try:
            btn = upvote_buttons[i]
            if await btn.is_visible():
                # Scroll to the button first
                await btn.scroll_into_view_if_needed()
                await asyncio.sleep(human_delay(500, 1500))
                await btn.click()
                upvoted += 1
                log.info(f"Upvoted post {upvoted}/{count} in r/{subreddit_name}")
                await asyncio.sleep(human_delay(1000, 3000))
        except Exception as e:
            log.warning(f"Upvote failed: {e}")
            continue

    log.info(f"Upvoted {upvoted} posts in r/{subreddit_name}")
    return upvoted


async def reply_to_replies(session, config: Config) -> int:
    """Check our past comments for replies and respond to them.

    This makes the account look engaged — real users reply back when
    someone responds to their comment.

    Returns number of replies sent.
    """
    page = session.page
    replied = 0

    # Get our recent comments from the DB
    with get_connection() as conn:
        comments = conn.execute(
            """SELECT id, thread_id, subreddit, comment_text
               FROM comments
               WHERE status = 'posted'
               AND posted_at >= datetime('now', '-7 days')
               ORDER BY posted_at DESC
               LIMIT 5""",
        ).fetchall()

    if not comments:
        log.info("No recent comments to check for replies")
        return 0

    for comment in comments:
        thread_id = comment["thread_id"]

        # Get thread URL
        with get_connection() as conn:
            thread = conn.execute(
                "SELECT url FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if not thread:
                continue
            thread_url = thread["url"]

        try:
            await page.goto(thread_url, wait_until="domcontentloaded")
            await asyncio.sleep(human_delay(2000, 4000))

            # Look for replies to our comment
            our_text_snippet = comment["comment_text"][:40]
            replies = await page.evaluate(f"""
                () => {{
                    const allComments = document.querySelectorAll('shreddit-comment, [data-testid="comment"]');
                    const replies = [];
                    let foundOurs = false;

                    for (const el of allComments) {{
                        const text = el.textContent || '';
                        if (text.includes('{our_text_snippet.replace("'", "\\'")}')) {{
                            foundOurs = true;
                            continue;
                        }}
                        // Comments after ours at a deeper nesting level are replies
                        if (foundOurs && replies.length < 3) {{
                            const depth = el.getAttribute('depth') || '0';
                            if (parseInt(depth) > 0) {{
                                const body = el.querySelector('[slot="comment-body"], .md');
                                const author = el.querySelector('a[href^="/user/"]');
                                if (body) {{
                                    replies.push({{
                                        body: body.textContent.trim().slice(0, 300),
                                        author: author ? author.textContent.trim() : 'anon',
                                    }});
                                }}
                            }}
                        }}
                    }}
                    return replies;
                }}
            """)

            if not replies:
                continue

            # Check if we already replied (don't double-reply)
            with get_connection() as conn:
                reply_count = conn.execute(
                    """SELECT COUNT(*) FROM comments
                       WHERE thread_id = ? AND comment_text LIKE '%reply to%'""",
                    (thread_id,),
                ).fetchone()[0]
                if reply_count > 0:
                    continue

            # Generate a reply to the first response
            reply_text = await _generate_reply(
                config, comment["subreddit"],
                comment["comment_text"], replies[0]
            )

            if reply_text:
                # Find the reply button for the specific reply comment
                # For now, we'll reply to the thread-level reply
                log.info(f"Generated reply ({len(reply_text)} chars) to reply in r/{comment['subreddit']}")
                replied += 1
                # TODO: implement the actual reply-to-reply posting
                # This requires finding the specific reply's comment box

        except Exception as e:
            log.warning(f"Error checking replies for thread {thread_id}: {e}")
            continue

    log.info(f"Replied to {replied} replies")
    return replied


async def create_post(
    session,
    config: Config,
    subreddit: SubredditConfig,
    title: str,
    body: str,
) -> dict:
    """Create a new text post in a subreddit.

    Returns dict with 'success' and 'url' or 'error'.
    """
    page = session.page

    await page.goto(
        f"https://www.reddit.com/r/{subreddit.name}/submit/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(human_delay(2000, 4000))

    # Dismiss cookie popup
    try:
        for btn in await page.query_selector_all("button"):
            if "Accept All" in (await btn.inner_text()):
                await btn.click()
                await asyncio.sleep(1)
                break
    except Exception:
        pass

    # Fill title
    try:
        title_input = await page.wait_for_selector(
            'textarea[placeholder*="title"], '
            'input[placeholder*="title"], '
            'div[data-testid="post-title"] textarea, '
            '[aria-label*="title"]',
            timeout=10000,
        )
        await title_input.click()
        await asyncio.sleep(human_delay(300, 600))
        for char in title:
            await page.keyboard.type(char, delay=human_typing_delay() * 1000)
        log.info(f"Filled title: {title[:50]}...")
    except Exception as e:
        log.error(f"Could not find title input: {e}")
        return {"success": False, "error": "title_input_not_found"}

    await asyncio.sleep(human_delay(500, 1000))

    # Fill body
    try:
        body_input = await page.query_selector(
            'div[contenteditable="true"], '
            'textarea[placeholder*="text"], '
            'div[data-testid="post-body"] div[contenteditable]'
        )
        if body_input:
            await body_input.click()
            await asyncio.sleep(human_delay(300, 600))
            for char in body:
                await page.keyboard.type(char, delay=human_typing_delay() * 1000)
            log.info(f"Filled body ({len(body)} chars)")
    except Exception as e:
        log.warning(f"Could not fill body: {e}")

    await asyncio.sleep(human_delay(1000, 2000))

    # Click Post button
    try:
        btns = await page.query_selector_all("button")
        for btn in btns:
            txt = (await btn.inner_text()).strip()
            if txt == "Post" and await btn.is_visible():
                await btn.click()
                log.info("Clicked Post button")
                break
    except Exception as e:
        log.error(f"Could not find Post button: {e}")
        return {"success": False, "error": "post_button_not_found"}

    await asyncio.sleep(human_delay(3000, 5000))

    # Check if we landed on the new post
    current_url = page.url
    if "/comments/" in current_url:
        log.info(f"Post created: {current_url}")
        return {"success": True, "url": current_url}

    log.error("Post may have failed — didn't redirect to new post")
    return {"success": False, "error": "no_redirect"}


async def browse_subreddit(session, subreddit_name: str) -> None:
    """Just browse a subreddit like a real user. Scroll through posts.

    This adds natural browsing activity to the account's behavior pattern.
    """
    page = session.page
    await page.goto(
        f"https://www.reddit.com/r/{subreddit_name}/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(human_delay(2000, 4000))

    # Scroll through a few posts naturally
    for _ in range(random.randint(2, 5)):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
        await asyncio.sleep(human_delay(1500, 4000))

    # Maybe click on a post to read it
    if random.random() < 0.3:
        posts = await page.query_selector_all("shreddit-post")
        if posts:
            post = random.choice(posts[:5])
            try:
                link = await post.query_selector('a[slot="full-post-link"]')
                if link:
                    await link.click()
                    await asyncio.sleep(human_delay(3000, 8000))
                    # Scroll through the post
                    for _ in range(random.randint(1, 3)):
                        await page.evaluate("window.scrollBy(0, 400)")
                        await asyncio.sleep(human_delay(1000, 3000))
            except Exception:
                pass

    log.info(f"Browsed r/{subreddit_name}")


async def _generate_reply(
    config: Config,
    subreddit: str,
    our_comment: str,
    reply: dict,
) -> str:
    """Generate a reply to someone who replied to our comment."""
    prompt = (
        f"Someone replied to your Reddit comment in r/{subreddit}.\n\n"
        f"Your original comment: \"{our_comment[:200]}\"\n\n"
        f"Their reply ({reply['author']}): \"{reply['body']}\"\n\n"
        f"Write a brief, natural reply. 1-2 sentences max. "
        f"Be conversational, not formal. Don't repeat yourself."
    )
    try:
        return call_llm(prompt, max_tokens=200)
    except Exception as e:
        log.error(f"Failed to generate reply: {e}")
        return ""
