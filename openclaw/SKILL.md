---
name: reddit-agent
description: "Autonomous Reddit engagement agent. Scans subreddits, generates human-like comments, posts via stealth browser, learns from feedback. Install: clone repo + run install.sh. Only needs Reddit username/password. Commands: reddit-agent, reddit-agent --feedback, reddit-agent --digest. Use when: user wants Reddit automation, Reddit posting, Reddit engagement, check Reddit performance."
allowed-tools: Bash(reddit-agent *), Bash(cat ~/.reddit-agent/data/*), Bash(~/.reddit-agent/.venv/bin/python *), Bash(cd ~/.reddit-agent *), Read, Edit
---

# Reddit Agent

Autonomous Reddit engagement agent. Browser-based posting with AI-generated comments.

## First-Time Setup

When the user says "install the reddit agent" or similar:

1. **Ask for Reddit credentials only** — username and password. Nothing else is needed.
2. Run the installer:

```bash
REDDIT_USERNAME="<username>" REDDIT_PASSWORD="<password>" \
  ~/.reddit-agent/install.sh --non-interactive
```

Or if not yet cloned:
```bash
git clone --depth 1 https://github.com/sohazur/reddit-agent.git ~/.reddit-agent
cd ~/.reddit-agent && REDDIT_USERNAME="<username>" REDDIT_PASSWORD="<password>" ./install.sh --non-interactive
```

3. Verify: `reddit-agent --digest` (should output a report, even if empty on first run)

**DO NOT ask for:**
- Anthropic/OpenAI API key (you already have LLM access)
- Slack webhook (you ARE the notification channel — just message the user)
- Any other credentials

## Running

```bash
reddit-agent              # Run one engagement cycle
reddit-agent --feedback   # Check karma on past comments, detect shadowbans
reddit-agent --digest     # Generate daily performance report
```

After running, **report the results directly to the user** in chat. You are the Slack replacement.

## Configuration

**Subreddits** — edit `~/.reddit-agent/data/subreddits.yaml`:
```yaml
subreddits:
  - name: SEO
    keywords: [AI search, GEO, llms.txt]
    max_daily_comments: 3
    tone: "Technical, data-driven."
    notes: "No self-promotion."
```

When the user says "add r/marketing" or "post in r/SEO", edit this file.

**Posting limits** — edit `~/.reddit-agent/.env`:
- `MAX_COMMENTS_PER_DAY` — default 5
- `MIN_COMMENT_INTERVAL_MINUTES` — default 20
- `QUALITY_THRESHOLD` — default 7 (1-10 scale)

## Monitoring

Read these files to report on performance:

| What | Command |
|---|---|
| What the agent learned | `cat ~/.reddit-agent/data/learnings.md` |
| Subreddit intel report | `cat ~/.reddit-agent/data/subreddit_reports/SEO.md` |
| Recent activity | `~/.reddit-agent/.venv/bin/python -c "from src.db import get_daily_summary; import json; print(json.dumps(get_daily_summary(), indent=2))"` |
| Error screenshots | `ls ~/.reddit-agent/data/screenshots/` |

## Responding to User Requests

| User says | What to do |
|---|---|
| "Install the reddit agent" | Ask for Reddit username/password, run installer |
| "Run the reddit bot" | `reddit-agent` then report results |
| "How's Reddit going?" | `reddit-agent --digest` then summarize |
| "Add r/marketing" | Edit subreddits.yaml, add the subreddit |
| "Post more often" | Edit .env, increase MAX_COMMENTS_PER_DAY |
| "Stop posting" | Edit .env, set MAX_COMMENTS_PER_DAY=0 |
| "What did you learn?" | `cat ~/.reddit-agent/data/learnings.md` |
| "Check for shadowbans" | `reddit-agent --feedback` then report |

## How It Works (for your context)

Each cycle: scans target subreddits via browser → evaluates threads (Claude) → generates human-like comments → quality-gates them (naturalness, subtlety) → posts via stealth headless browser → later checks karma and shadowbans → writes learnings for next time.

Anti-detection: randomized user agents, human typing delays, viewport rotation, 15-20min spacing between posts.
