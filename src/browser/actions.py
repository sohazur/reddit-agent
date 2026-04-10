"""Browser actions for Reddit interaction.

Navigate, extract content, post comments, and verify results.
"""

import asyncio
import re

from playwright.async_api import Page

from src.browser.stealth import human_delay, human_typing_delay
from src.config import SCREENSHOTS_DIR
from src.log import get_logger

log = get_logger("actions")


async def extract_search_results(
    session,  # RedditSession
    search_url: str,
    limit: int = 15,
) -> list[dict]:
    """Navigate to a Reddit search URL and extract thread results.

    Returns a list of dicts with: id, title, url, score, comment_count.
    """
    page = session.page
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(human_delay(2000, 4000))

    # Scroll down to load more results
    for _ in range(2):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(human_delay(800, 1500))

    results = await page.evaluate(f"""
        () => {{
            const posts = [];

            // Primary: shreddit-post elements (modern Reddit)
            const shredditPosts = document.querySelectorAll('shreddit-post');
            for (const el of shredditPosts) {{
                if (posts.length >= {limit}) break;

                const id = el.getAttribute('id') || el.getAttribute('thingid') || '';
                const title = el.getAttribute('post-title') || '';
                const permalink = el.getAttribute('permalink') || '';
                const score = parseInt(el.getAttribute('score') || '0') || 0;
                const commentCount = parseInt(el.getAttribute('comment-count') || '0') || 0;

                let url = permalink;
                if (url && !url.startsWith('http')) {{
                    url = 'https://www.reddit.com' + url;
                }}

                if (title && (id || url)) {{
                    posts.push({{
                        id: id.replace('t3_', ''),
                        title,
                        url,
                        score,
                        comment_count: commentCount
                    }});
                }}
            }}

            // Fallback: older Reddit layouts
            if (posts.length === 0) {{
                const oldPosts = document.querySelectorAll('div[data-testid="post-container"], div.Post, article');
                for (const el of oldPosts) {{
                    if (posts.length >= {limit}) break;
                    const titleEl = el.querySelector('h3, [slot="title"]');
                    const title = titleEl ? titleEl.textContent.trim() : '';
                    const linkEl = el.querySelector('a[href*="comments"]');
                    let url = linkEl ? linkEl.getAttribute('href') : '';
                    if (url && !url.startsWith('http')) url = 'https://www.reddit.com' + url;
                    const id = el.getAttribute('id') || el.getAttribute('data-fullname') || '';
                    if (title) {{
                        posts.push({{ id: id.replace('t3_', ''), title, url, score: 0, comment_count: 0 }});
                    }}
                }}
            }}

            return posts;
        }}
    """)

    log.info(f"Extracted {len(results)} search results")
    return results


async def extract_thread_content(
    session,  # RedditSession
    thread_url: str,
    max_comments: int = 10,
) -> dict:
    """Navigate to a thread and extract title, body, and top comments."""
    page = session.page
    await page.goto(thread_url, wait_until="domcontentloaded")
    await asyncio.sleep(human_delay(2000, 4000))

    # Scroll to load comments
    await page.evaluate("window.scrollBy(0, 500)")
    await asyncio.sleep(human_delay(1000, 2000))

    content = await page.evaluate(f"""
        () => {{
            // Extract post title
            const titleEl = document.querySelector(
                'h1, [data-testid="post-title"], [slot="title"]'
            );
            const title = titleEl ? titleEl.textContent.trim() : '';

            // Extract post body
            const bodyEl = document.querySelector(
                '[data-testid="post-content"] .md, '
                + '[slot="text-body"], '
                + '.Post .RichTextJSON-root, '
                + '.selftext'
            );
            const body = bodyEl ? bodyEl.textContent.trim() : '';

            // Extract comments
            const comments = [];
            const commentEls = document.querySelectorAll(
                '[data-testid="comment"], '
                + 'shreddit-comment, '
                + '.Comment'
            );

            for (const el of commentEls) {{
                if (comments.length >= {max_comments}) break;

                const authorEl = el.querySelector(
                    'a[href^="/user/"], [data-testid="comment_author"]'
                );
                const author = authorEl ? authorEl.textContent.trim() : 'anon';

                const bodyEl = el.querySelector(
                    '.md, [slot="comment-body"], .RichTextJSON-root'
                );
                const commentBody = bodyEl
                    ? bodyEl.textContent.trim().slice(0, 500)
                    : '';

                const scoreEl = el.querySelector(
                    '[data-testid="comment-score"], .score'
                );
                const score = scoreEl
                    ? parseInt(scoreEl.textContent.replace(/[^0-9-]/g, '')) || 0
                    : 0;

                if (commentBody) {{
                    comments.push({{ author, body: commentBody, score }});
                }}
            }}

            return {{ title, body: body.slice(0, 3000), comments }};
        }}
    """)

    log.info(
        f"Extracted thread: '{content.get('title', '')[:50]}' "
        f"with {len(content.get('comments', []))} comments"
    )
    return content


async def extract_subreddit_data(
    session,  # RedditSession
    subreddit_name: str,
) -> dict:
    """Gather data about a subreddit for the intelligence report.

    Visits the subreddit, extracts top posts, sample comments, and sidebar rules.
    """
    page = session.page
    data = {"posts": [], "sample_comments": [], "sidebar": ""}

    # Get hot posts
    await page.goto(
        f"https://www.reddit.com/r/{subreddit_name}/hot/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(human_delay(2000, 4000))

    # Scroll to load more
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(human_delay(800, 1500))

    posts = await page.evaluate("""
        () => {
            const posts = [];
            // Modern Reddit uses shreddit-post web components with attributes
            const els = document.querySelectorAll('shreddit-post');
            for (const el of els) {
                if (posts.length >= 30) break;
                posts.push({
                    title: el.getAttribute('post-title') || '',
                    score: parseInt(el.getAttribute('score') || '0') || 0,
                    comment_count: parseInt(el.getAttribute('comment-count') || '0') || 0,
                    url: el.getAttribute('permalink') || '',
                });
            }
            // Fallback for older layouts
            if (posts.length === 0) {
                const oldEls = document.querySelectorAll('div[data-testid="post-container"], article');
                for (const el of oldEls) {
                    if (posts.length >= 30) break;
                    const titleEl = el.querySelector('h3, [slot="title"]');
                    posts.push({
                        title: titleEl ? titleEl.textContent.trim() : '',
                        score: 0,
                        comment_count: 0,
                        url: '',
                    });
                }
            }
            return posts;
        }
    """)
    data["posts"] = posts

    # Visit top post to get sample comments
    if posts and posts[0].get("url"):
        url = posts[0]["url"]
        if not url.startswith("http"):
            url = "https://www.reddit.com" + url

        thread = await extract_thread_content(session, url, max_comments=10)
        data["sample_comments"] = thread.get("comments", [])

    # Try to get sidebar/rules
    try:
        await page.goto(
            f"https://www.reddit.com/r/{subreddit_name}/about/rules/",
            wait_until="domcontentloaded",
        )
        await asyncio.sleep(human_delay(1500, 3000))

        sidebar = await page.evaluate("""
            () => {
                const rules = [];
                const ruleEls = document.querySelectorAll(
                    '[data-testid="rule"], .rule-description, article'
                );
                for (const el of ruleEls) {
                    rules.push(el.textContent.trim());
                }
                return rules.join('\\n');
            }
        """)
        data["sidebar"] = sidebar
    except Exception as e:
        log.warning(f"Could not fetch rules for r/{subreddit_name}: {e}")

    return data


async def post_comment(
    session,  # RedditSession
    thread_url: str,
    comment_text: str,
) -> dict:
    """Navigate to a thread and post a comment.

    Returns dict with 'success', 'comment_id' (if successful), 'error' (if failed).
    """
    page = session.page
    await page.goto(thread_url, wait_until="domcontentloaded")
    await asyncio.sleep(human_delay(2000, 4000))

    # Check if thread is locked
    is_locked = await page.evaluate("""
        () => {
            const locked = document.querySelector(
                '[data-testid="locked-icon"], .locked-icon, [aria-label*="locked"]'
            );
            return !!locked;
        }
    """)
    if is_locked:
        log.warning(f"Thread is locked: {thread_url}")
        return {"success": False, "error": "thread_locked"}

    # Find and click the comment box
    try:
        # Reddit's comment box can be a contenteditable div or textarea
        comment_box = await page.wait_for_selector(
            'div[contenteditable="true"][role="textbox"], '
            'textarea[placeholder*="comment"], '
            'div[data-testid="comment-submission-form-richtext"] div[contenteditable], '
            '[name="body"]',
            timeout=10000,
        )
    except Exception:
        log.error("Could not find comment box")
        await _screenshot_error(page, "no_comment_box")
        return {"success": False, "error": "comment_box_not_found"}

    # Click to focus
    await comment_box.click()
    await asyncio.sleep(human_delay(500, 1000))

    # Type the comment with human-like delays
    for char in comment_text:
        await page.keyboard.type(char, delay=human_typing_delay() * 1000)

    await asyncio.sleep(human_delay(1000, 2000))

    # Find and click the submit button
    try:
        submit_btn = await page.wait_for_selector(
            'button[type="submit"]:has-text("Comment"), '
            'button:has-text("Comment"), '
            'button[data-testid="comment-submission-form-submit"]',
            timeout=5000,
        )
        await submit_btn.click()
    except Exception:
        log.error("Could not find submit button")
        await _screenshot_error(page, "no_submit_button")
        return {"success": False, "error": "submit_button_not_found"}

    # Wait for the comment to appear
    await asyncio.sleep(human_delay(3000, 5000))

    # Check for errors (rate limit, etc.)
    error_text = await page.evaluate("""
        () => {
            const errorEl = document.querySelector(
                '[class*="error"], [data-testid="comment-error"]'
            );
            return errorEl ? errorEl.textContent.trim() : '';
        }
    """)

    if error_text:
        log.error(f"Reddit posting error: {error_text}")
        return {"success": False, "error": error_text}

    # Try to extract the comment ID from the page
    comment_id = await page.evaluate("""
        () => {
            // Get the most recent comment by the logged-in user
            const comments = document.querySelectorAll(
                '[data-testid="comment"], shreddit-comment'
            );
            const last = comments[comments.length - 1];
            if (last) {
                return last.getAttribute('id')
                    || last.getAttribute('data-fullname')
                    || last.getAttribute('thingid')
                    || 'unknown';
            }
            return 'unknown';
        }
    """)

    log.info(f"Comment posted successfully (id: {comment_id})")
    return {"success": True, "comment_id": comment_id}


async def check_comment_visible(
    incognito_page: Page,
    thread_url: str,
    comment_text_snippet: str,
) -> bool:
    """Check if a comment is visible to a logged-out user.

    Used for shadowban detection. Opens the thread in an incognito
    context and searches for the comment text.
    """
    try:
        await incognito_page.goto(thread_url, wait_until="domcontentloaded")
        await asyncio.sleep(human_delay(2000, 4000))

        # Scroll to load comments
        for _ in range(3):
            await incognito_page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(human_delay(500, 1000))

        # Search for our comment text in the page
        # Use first 50 chars as a snippet to match
        snippet = comment_text_snippet[:50].replace("'", "\\'")
        found = await incognito_page.evaluate(f"""
            () => {{
                return document.body.innerText.includes('{snippet}');
            }}
        """)

        return found

    except Exception as e:
        log.error(f"Shadowban check failed: {e}")
        return True  # Assume visible on error (fail open)


async def _screenshot_error(page: Page, name: str) -> None:
    """Take a screenshot on error."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"error_{name}_{timestamp}.png"
    try:
        await page.screenshot(path=str(path))
        log.info(f"Error screenshot: {path}")
    except Exception:
        pass
