"""Scan subreddits for relevant threads using browser-use."""

import json
from dataclasses import dataclass

from src.config import SubredditConfig
from src.db import has_commented_on_thread, record_thread
from src.log import get_logger

log = get_logger("scanner")


@dataclass
class DiscoveredThread:
    id: str
    subreddit: str
    title: str
    body: str
    url: str
    score: int
    comment_count: int
    top_comments: list[dict]


async def scan_subreddit(
    browser_session,
    subreddit: SubredditConfig,
    limit: int = 15,
) -> list[DiscoveredThread]:
    """Scan a subreddit for relevant threads using the browser.

    Uses Reddit's search within the subreddit for each keyword,
    then deduplicates and returns fresh threads.
    """
    log.info(f"Scanning r/{subreddit.name} for threads")
    seen_ids: set[str] = set()
    threads: list[DiscoveredThread] = []

    for keyword in subreddit.keywords:
        try:
            found = await _search_subreddit(
                browser_session, subreddit.name, keyword, limit=limit
            )
            for thread in found:
                if thread.id in seen_ids:
                    continue
                if has_commented_on_thread(thread.id):
                    log.info(f"Skipping {thread.id} — already commented")
                    continue
                seen_ids.add(thread.id)
                threads.append(thread)

                record_thread(
                    thread_id=thread.id,
                    subreddit=subreddit.name,
                    title=thread.title,
                    url=thread.url,
                    score=thread.score,
                    comment_count=thread.comment_count,
                )
        except Exception as e:
            log.error(f"Error scanning r/{subreddit.name} for '{keyword}': {e}")
            continue

    log.info(f"Found {len(threads)} new threads in r/{subreddit.name}")
    return threads


async def _search_subreddit(
    browser_session,
    subreddit_name: str,
    keyword: str,
    limit: int = 15,
) -> list[DiscoveredThread]:
    """Search a subreddit for a keyword using the browser.

    Navigates to Reddit search, extracts thread data from the page.
    """
    from src.browser.actions import extract_search_results

    search_url = (
        f"https://www.reddit.com/r/{subreddit_name}/search/"
        f"?q={keyword}&restrict_sr=1&sort=new&t=week"
    )

    log.info(f"Searching r/{subreddit_name} for '{keyword}'")

    try:
        results = await extract_search_results(browser_session, search_url, limit)
        return [
            DiscoveredThread(
                id=r["id"],
                subreddit=subreddit_name,
                title=r["title"],
                body=r.get("body", ""),
                url=r["url"],
                score=r.get("score", 0),
                comment_count=r.get("comment_count", 0),
                top_comments=r.get("top_comments", []),
            )
            for r in results
        ]
    except Exception as e:
        log.error(f"Search failed for r/{subreddit_name} '{keyword}': {e}")
        return []


async def read_thread_details(
    browser_session,
    thread_url: str,
    max_comments: int = 10,
) -> dict:
    """Navigate to a thread and extract full details including top comments."""
    from src.browser.actions import extract_thread_content

    try:
        return await extract_thread_content(browser_session, thread_url, max_comments)
    except Exception as e:
        log.error(f"Failed to read thread {thread_url}: {e}")
        return {"title": "", "body": "", "comments": []}
