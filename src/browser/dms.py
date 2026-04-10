"""Reddit DM management: read, reply, and proactive outreach.

Handles:
- Reading incoming DMs and replying intelligently
- Finding posts/comments where users ask for help → proactive DM
- Lead tracking for potential customers
"""

import asyncio
import json
from datetime import datetime

from src.browser.stealth import human_delay, human_typing_delay
from src.config import Config, DATA_DIR
from src.db import get_connection
from src.llm import call_llm
from src.log import get_logger

log = get_logger("dms")

LEADS_PATH = DATA_DIR / "leads.json"


async def check_and_reply_dms(session, config: Config) -> dict:
    """Read incoming DMs and reply to ones that haven't been answered.

    Returns dict with counts: checked, replied, new_leads.
    """
    page = session.page
    results = {"checked": 0, "replied": 0, "new_leads": 0}

    log.info("Checking DMs")

    await page.goto(
        "https://www.reddit.com/message/messages/",
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

    # Extract DMs from the inbox
    messages = await page.evaluate("""
        () => {
            const msgs = [];
            const elements = document.querySelectorAll(
                '[data-testid="message"], .message, article'
            );
            for (const el of elements) {
                if (msgs.length >= 10) break;
                const author = el.querySelector('a[href^="/user/"]');
                const subject = el.querySelector('[data-testid="message-subject"], .subject, h4');
                const body = el.querySelector('[data-testid="message-body"], .md, p');
                const isNew = el.querySelector('.unread, [class*="unread"]');

                if (body && body.textContent.trim()) {
                    msgs.push({
                        author: author ? author.textContent.trim().replace('u/', '') : 'unknown',
                        subject: subject ? subject.textContent.trim() : '',
                        body: body.textContent.trim().slice(0, 500),
                        isNew: !!isNew,
                    });
                }
            }

            // Fallback: get page text
            if (msgs.length === 0) {
                return [{
                    author: 'RAW',
                    subject: 'page_text',
                    body: document.body.innerText.slice(0, 2000),
                    isNew: false,
                }];
            }
            return msgs;
        }
    """)

    for msg in messages:
        if msg.get("author") == "RAW":
            continue

        results["checked"] += 1

        # Skip if we already replied to this user
        if _already_replied(msg["author"]):
            continue

        # Generate a reply based on objective
        reply_text = await _generate_dm_reply(config, msg)
        if not reply_text:
            continue

        # Track as a lead if relevant to objective
        if _is_potential_lead(config, msg):
            _save_lead(msg, "inbound_dm")
            results["new_leads"] += 1

        # TODO: Actually send the reply via Reddit's DM interface
        # This requires navigating to the chat/message reply form
        log.info(
            f"DM from u/{msg['author']}: {msg['body'][:80]}... "
            f"→ Would reply: {reply_text[:80]}..."
        )
        _record_dm_reply(msg["author"], msg["body"], reply_text)
        results["replied"] += 1

    log.info(
        f"DMs: {results['checked']} checked, "
        f"{results['replied']} replied, {results['new_leads']} leads"
    )
    return results


async def find_outreach_opportunities(
    session, config: Config, subreddit_name: str
) -> list[dict]:
    """Scan a subreddit for posts where people are asking for help.

    Looks for posts like "looking for recommendations", "need help with",
    "can anyone suggest", etc. — these are DM outreach opportunities.

    Returns list of opportunities with author, post title, and suggested DM.
    """
    page = session.page
    opportunities = []

    await page.goto(
        f"https://www.reddit.com/r/{subreddit_name}/new/",
        wait_until="domcontentloaded",
    )
    await asyncio.sleep(human_delay(2000, 4000))

    # Get recent posts
    posts = await page.evaluate("""
        () => {
            const posts = [];
            const els = document.querySelectorAll('shreddit-post');
            for (const el of els) {
                if (posts.length >= 15) break;
                const title = el.getAttribute('post-title') || '';
                const author = el.getAttribute('author') || '';
                const permalink = el.getAttribute('permalink') || '';
                posts.push({ title, author, url: permalink });
            }
            return posts;
        }
    """)

    # Use LLM to identify outreach opportunities
    if not posts:
        return []

    posts_text = "\n".join(
        f"- \"{p['title']}\" by u/{p['author']}"
        for p in posts[:15]
    )

    objective = config.objective or "help people and build connections"

    prompt = (
        f"You are scanning r/{subreddit_name} for DM outreach opportunities.\n\n"
        f"Your objective: {objective}\n\n"
        f"Recent posts:\n{posts_text}\n\n"
        f"Which of these posts are from people who might benefit from a helpful DM? "
        f"Look for: asking for recommendations, needing help, seeking advice, "
        f"looking for tools/services, frustrated with a problem.\n\n"
        f"Return ONLY a JSON array of objects with 'title' and 'reason' (one sentence "
        f"why this is an opportunity). Return empty array [] if none are good fits.\n"
        f"```json\n"
    )

    try:
        response = call_llm(prompt, max_tokens=500)
        if "```" in response:
            response = response.split("```json")[-1].split("```")[0].strip()
            if not response:
                response = "[]"

        opps = json.loads(response)

        for opp in opps:
            # Match back to the original post
            for post in posts:
                if opp.get("title", "").lower() in post["title"].lower():
                    if not _already_dmed(post["author"]):
                        opportunities.append({
                            "author": post["author"],
                            "title": post["title"],
                            "url": post["url"],
                            "reason": opp.get("reason", ""),
                            "subreddit": subreddit_name,
                        })
                    break

    except (json.JSONDecodeError, Exception) as e:
        log.warning(f"Failed to parse outreach opportunities: {e}")

    log.info(f"Found {len(opportunities)} outreach opportunities in r/{subreddit_name}")
    return opportunities


async def send_dm(
    session, config: Config, username: str, subject: str, message: str
) -> bool:
    """Send a DM to a Reddit user.

    Returns True if sent successfully.
    """
    page = session.page

    log.info(f"Sending DM to u/{username}")

    await page.goto(
        f"https://www.reddit.com/message/compose/?to={username}",
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

    # Fill subject
    try:
        subject_input = await page.query_selector(
            'input[name="subject"], '
            'textarea[placeholder*="subject"], '
            '[aria-label*="subject"]'
        )
        if subject_input:
            await subject_input.click()
            await asyncio.sleep(human_delay(300, 600))
            for char in subject:
                await page.keyboard.type(char, delay=human_typing_delay() * 1000)
    except Exception as e:
        log.warning(f"Could not fill DM subject: {e}")

    await asyncio.sleep(human_delay(500, 1000))

    # Fill message body
    try:
        body_input = await page.query_selector(
            'textarea[name="message"], '
            'div[contenteditable="true"], '
            'textarea[placeholder*="message"]'
        )
        if body_input:
            await body_input.click()
            await asyncio.sleep(human_delay(300, 600))
            for char in message:
                await page.keyboard.type(char, delay=human_typing_delay() * 1000)
    except Exception as e:
        log.error(f"Could not fill DM body: {e}")
        return False

    await asyncio.sleep(human_delay(1000, 2000))

    # Click send
    try:
        for btn in await page.query_selector_all("button"):
            txt = (await btn.inner_text()).strip()
            if txt in ("Send", "Send message", "Submit") and await btn.is_visible():
                await btn.click()
                log.info(f"DM sent to u/{username}")
                _record_dm_sent(username, subject, message)
                _save_lead(
                    {"author": username, "subject": subject, "body": message},
                    "outbound_dm",
                )
                return True
    except Exception as e:
        log.error(f"Failed to send DM: {e}")

    return False


async def generate_outreach_dm(config: Config, opportunity: dict) -> tuple[str, str]:
    """Generate a DM subject and message for an outreach opportunity.

    Returns (subject, message) tuple.
    """
    objective = config.objective or "be helpful"
    prompt = (
        f"You need to write a short, friendly Reddit DM to u/{opportunity['author']}.\n\n"
        f"They posted: \"{opportunity['title']}\" in r/{opportunity['subreddit']}\n"
        f"Why this is relevant: {opportunity.get('reason', '')}\n\n"
        f"Your objective (implicit, don't state it): {objective}\n\n"
        f"Rules:\n"
        f"- Be genuinely helpful, not salesy\n"
        f"- Reference their specific post/problem\n"
        f"- Offer a specific insight or suggestion\n"
        f"- Keep it 2-4 sentences\n"
        f"- Don't pitch or link anything unless they asked\n"
        f"- Sound like a person, not a business\n\n"
        f"Return ONLY a JSON object:\n"
        f'```json\n{{"subject": "short subject line", "message": "the dm body"}}\n```'
    )

    try:
        response = call_llm(prompt, max_tokens=300)
        if "```" in response:
            response = response.split("```json")[-1].split("```")[0].strip()
        data = json.loads(response)
        return data.get("subject", ""), data.get("message", "")
    except Exception as e:
        log.error(f"Failed to generate outreach DM: {e}")
        return "", ""


# ─── Lead tracking ─────────────────────────────────


def _save_lead(msg: dict, source: str) -> None:
    """Save a potential lead to the leads file."""
    LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)

    leads = []
    if LEADS_PATH.exists():
        try:
            leads = json.loads(LEADS_PATH.read_text())
        except Exception:
            leads = []

    leads.append({
        "username": msg.get("author", "unknown"),
        "source": source,
        "subject": msg.get("subject", ""),
        "body": msg.get("body", "")[:200],
        "timestamp": datetime.utcnow().isoformat(),
    })

    LEADS_PATH.write_text(json.dumps(leads, indent=2))
    log.info(f"Lead saved: u/{msg.get('author')} ({source})")


def _is_potential_lead(config: Config, msg: dict) -> bool:
    """Quick check if a DM sender might be a potential lead."""
    if not config.objective:
        return False
    # If they're asking about something related to our objective, it's a lead
    keywords = config.objective.lower().split()
    text = f"{msg.get('subject', '')} {msg.get('body', '')}".lower()
    matches = sum(1 for kw in keywords if kw in text)
    return matches >= 2


# ─── Dedup tracking ────────────────────────────────


def _already_replied(username: str) -> bool:
    """Check if we already replied to this user's DM."""
    with get_connection() as conn:
        # Use a simple tracking approach — check if we have a record
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM dm_log WHERE username = ? AND direction = 'reply'",
                (username,),
            ).fetchone()
            return row[0] > 0
        except Exception:
            # Table might not exist yet
            return False


def _already_dmed(username: str) -> bool:
    """Check if we already sent an outreach DM to this user."""
    with get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM dm_log WHERE username = ? AND direction = 'outbound'",
                (username,),
            ).fetchone()
            return row[0] > 0
        except Exception:
            return False


def _record_dm_reply(username: str, their_msg: str, our_reply: str) -> None:
    """Record that we replied to a DM."""
    _ensure_dm_table()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO dm_log (username, direction, their_text, our_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, "reply", their_msg[:500], our_reply[:500], datetime.utcnow().isoformat()),
        )


def _record_dm_sent(username: str, subject: str, message: str) -> None:
    """Record that we sent an outreach DM."""
    _ensure_dm_table()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO dm_log (username, direction, their_text, our_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, "outbound", subject, message[:500], datetime.utcnow().isoformat()),
        )


def _ensure_dm_table() -> None:
    """Create the dm_log table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dm_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                direction TEXT NOT NULL,
                their_text TEXT,
                our_text TEXT,
                created_at TEXT NOT NULL
            )
        """)
