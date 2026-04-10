# Reddit Agent — Manual Test Guide

Step-by-step instructions to test every feature locally.

## Prerequisites

```bash
cd ~/.reddit-agent   # or wherever it's installed
```

Make sure you have:
- A `.env` file with Reddit credentials
- `data/cookies.json` with valid Reddit cookies (if on a VM)
- Python venv set up (`.venv/` exists)

Quick check:
```bash
reddit-agent status
```

---

## Test 1: Health Check

```bash
reddit-agent status
```

**Expected:** Shows your Reddit username, daily limits, and passes Playwright/Chromium check.

---

## Test 2: Inbox Check (ban detection)

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.inbox import check_inbox, apply_inbox_actions
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    messages = await check_inbox(session)
    print(f'Found {len(messages)} inbox messages')
    for msg in messages:
        print(f'  [{\"BAN\" if msg.is_ban else \"REMOVAL\" if msg.is_removal else \"WARNING\"}] r/{msg.subreddit}: {msg.subject[:60]}')
    if messages:
        actions = apply_inbox_actions(messages, config)
        for a in actions:
            print(f'  Action: {a}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Lists any ban notices, removals, or mod warnings. If banned from a subreddit, it auto-disables it.

---

## Test 3: Karma Check

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.karma import get_account_karma
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    karma = await get_account_karma(session)
    print(f'Account karma: {karma}')
    for sub in config.subreddits:
        status = 'CAN POST' if karma >= sub.min_karma else 'BLOCKED (need {})'.format(sub.min_karma)
        print(f'  r/{sub.name}: {status}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Shows karma number and which subreddits are accessible.

---

## Test 4: Subreddit Scanning

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.scanner.subreddit import scan_subreddit
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]  # First subreddit
    print(f'Scanning r/{sub.name}...')
    threads = await scan_subreddit(session, sub, limit=5)
    print(f'Found {len(threads)} threads:')
    for t in threads:
        print(f'  [{t.score}] {t.title[:60]}')
        print(f'       {t.url}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Lists 5+ threads from the first subreddit with titles and scores.

---

## Test 5: Thread Evaluation

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.scanner.subreddit import scan_subreddit, read_thread_details
from src.intelligence.evaluator import evaluate_thread
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]
    threads = await scan_subreddit(session, sub, limit=3)
    if not threads:
        print('No threads found')
        await session.close()
        return
    t = threads[0]
    print(f'Evaluating: {t.title[:60]}')
    details = await read_thread_details(session, t.url)
    comments_text = chr(10).join(
        f'u/{c.get(\"author\")}: {c.get(\"body\", \"\")[:100]}'
        for c in details.get('comments', [])[:5]
    )
    score = await evaluate_thread(
        config=config, subreddit=sub,
        thread_title=t.title, thread_body=details.get('body', ''),
        thread_score=t.score, thread_comment_count=t.comment_count,
        thread_comments=comments_text, karma_mode=(sub.min_karma == 0),
    )
    print(f'Score: {score.total}/10')
    print(f'Reasoning: {score.reasoning}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Shows a thread score (0-10) with reasoning about why it's a good/bad opportunity.

---

## Test 6: Comment Generation + Quality Check

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.scanner.subreddit import scan_subreddit, read_thread_details
from src.intelligence.generator import generate_comment
from src.intelligence.quality_scorer import score_comment
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]
    threads = await scan_subreddit(session, sub, limit=3)
    if not threads:
        print('No threads found')
        await session.close()
        return
    t = threads[0]
    details = await read_thread_details(session, t.url)
    comments_text = chr(10).join(
        f'u/{c.get(\"author\")}: {c.get(\"body\", \"\")[:100]}'
        for c in details.get('comments', [])[:5]
    )
    print(f'Thread: {t.title[:60]}')
    print()
    comment = await generate_comment(
        config=config, subreddit=sub,
        thread_title=t.title, thread_body=details.get('body', ''),
        thread_comments=comments_text, karma_mode=(sub.min_karma == 0),
    )
    print(f'Generated comment:')
    print(f'  \"{comment}\"')
    print()
    quality = await score_comment(
        config=config, comment_text=comment,
        subreddit_name=sub.name, thread_title=t.title,
    )
    print(f'Quality: {quality.average}/10 (pass={quality.passed})')
    print(f'  Naturalness: {quality.naturalness}')
    print(f'  Relevance: {quality.relevance}')
    print(f'  Brand safety: {quality.brand_safety}')
    print(f'  Subtlety: {quality.subtlety}')
    if quality.issues:
        print(f'  Issues: {quality.issues}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Shows a generated comment and its quality scores. Should score 7+ to pass.

---

## Test 7: Upvoting

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.engage import upvote_posts
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]
    print(f'Upvoting in r/{sub.name}...')
    count = await upvote_posts(session, sub.name, count=2)
    print(f'Upvoted {count} posts')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Upvotes 2 posts and logs each one.

---

## Test 8: Browse (natural activity)

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.engage import browse_subreddit
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]
    print(f'Browsing r/{sub.name}...')
    await browse_subreddit(session, sub.name)
    print('Done browsing')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Scrolls through the subreddit, maybe clicks a post. Logs "Browsed r/...".

---

## Test 9: DM Check

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.dms import check_and_reply_dms
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    print('Checking DMs...')
    results = await check_and_reply_dms(session, config)
    print(f'DMs checked: {results[\"checked\"]}')
    print(f'Replies: {results[\"replied\"]}')
    print(f'New leads: {results[\"new_leads\"]}')
    await session.close()

asyncio.run(test())
"
```

**Expected:** Shows DM count. If there are new DMs, shows what it would reply.

---

## Test 10: Outreach Opportunity Scan

```bash
.venv/bin/python -c "
import asyncio
from src.browser.session import RedditSession
from src.browser.dms import find_outreach_opportunities, generate_outreach_dm
from src.config import load_config

async def test():
    config = load_config()
    session = await RedditSession(config).start()
    sub = config.subreddits[0]
    print(f'Scanning r/{sub.name} for outreach opportunities...')
    opps = await find_outreach_opportunities(session, config, sub.name)
    print(f'Found {len(opps)} opportunities:')
    for opp in opps[:3]:
        print(f'  u/{opp[\"author\"]}: \"{opp[\"title\"][:50]}\"')
        print(f'  Reason: {opp[\"reason\"]}')
        subject, msg = await generate_outreach_dm(config, opp)
        if subject:
            print(f'  DM subject: \"{subject}\"')
            print(f'  DM message: \"{msg[:100]}...\"')
        print()
    await session.close()

asyncio.run(test())
"
```

**Expected:** Lists posts from people asking for help, with draft DMs.

---

## Test 11: Full Cycle (dry run)

Run one complete cycle with limit of 1 comment:

```bash
# Temporarily set limit to 1
sed -i.bak 's/MAX_COMMENTS_PER_DAY=.*/MAX_COMMENTS_PER_DAY=1/' .env

# Run full cycle
reddit-agent run

# Restore limit
mv .env.bak .env
```

**Expected:** Full cycle log showing inbox check → karma → scan → evaluate → generate → quality check → post → upvote → browse → DM check → feedback → learn.

---

## Test 12: Digest Report

```bash
reddit-agent digest
```

**Expected:** Summary of today's activity — comments posted, survival rate, karma.

---

## Test 13: Change Objective

```bash
reddit-agent objective "Build authority in AI and machine learning communities"
reddit-agent status
```

**Expected:** Confirms objective updated.

---

## Test 14: Leads File

```bash
cat data/leads.json 2>/dev/null || echo "No leads yet"
```

**Expected:** JSON array of leads (empty if no DMs yet).

---

## Test 15: Learnings File

```bash
cat data/learnings.md 2>/dev/null || echo "No learnings yet"
```

**Expected:** Markdown file with what the agent learned from past cycles.

---

## Quick Smoke Test (all-in-one)

Run everything sequentially:

```bash
echo "=== Status ===" && reddit-agent status
echo "=== Digest ===" && reddit-agent digest
echo "=== Objective ===" && reddit-agent objective "Test objective for validation"
echo "=== Full cycle (1 comment) ==="
sed -i.bak 's/MAX_COMMENTS_PER_DAY=.*/MAX_COMMENTS_PER_DAY=1/' .env
reddit-agent run
mv .env.bak .env
echo "=== Done ==="
```
