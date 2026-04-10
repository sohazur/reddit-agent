# Reddit Agent

Autonomous Reddit engagement agent for [OpenClaw](https://openclaw.ai). Runs on any VM, no screen needed.

Tell your OpenClaw agent:

> "Install the Reddit agent from github.com/sohazur/reddit-agent"

It will ask for your Reddit username and password, set everything up, and start posting automatically.

## What It Does

- Browses Reddit subreddits and finds relevant threads
- Generates human-like comments using your OpenClaw's LLM
- Posts via a stealth headless browser (no API restrictions)
- Learns from feedback (karma, removals, shadowbans)
- Auto-builds karma on new accounts before targeting competitive subreddits
- Runs every 2 hours via OpenClaw cron

## Why Not Just Use OpenClaw Directly?

OpenClaw can browse the web, but this agent adds:

| Feature | OpenClaw alone | With reddit-agent |
|---|---|---|
| Headless VM (no screen) | Needs display | Playwright headless |
| Anti-detection | Basic browser | Stealth fingerprints, human typing |
| Datacenter IP blocked | Blocked by Reddit | Cookie-based auth bypass |
| Remember past posts | Forgets each session | SQLite persistent state |
| Rate limiting | Manual | Auto cadence management |
| Karma awareness | Manual | Auto-routes to right subreddits |
| Shadowban detection | Manual | Auto-checks after posting |
| Learning over time | No memory | Writes learnings.md, improves |

## Install

### Option 1: Tell your OpenClaw agent

```
Install the Reddit agent from github.com/sohazur/reddit-agent
```

Your agent will clone the repo, run the installer, and ask you for:
- Reddit username
- Reddit password
- Which subreddits to target (or use defaults)
- How many comments per day (default: 5)

### Option 2: Manual install

```bash
git clone https://github.com/sohazur/reddit-agent.git ~/.reddit-agent
cd ~/.reddit-agent
./install.sh
```

### Option 3: Non-interactive (for scripts/CI)

```bash
REDDIT_USERNAME=myuser REDDIT_PASSWORD=mypass \
  ~/.reddit-agent/install.sh --non-interactive
```

## Cookie Setup (Required for VMs)

Reddit blocks datacenter IPs. To bypass this, export cookies from a browser where you're logged in:

1. Log in to Reddit on your phone/laptop browser
2. Install a cookie export extension (Cookie-Editor, EditThisCookie)
3. Export cookies for reddit.com as JSON
4. Save to `~/.reddit-agent/data/cookies.json`

Or if you have `browser-cookie3` installed, the agent can extract cookies from Chrome automatically.

## Configuration

### Subreddits

Edit `~/.reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  - name: AskReddit           # Karma building (no min karma)
    max_daily_comments: 2
    min_karma: 0
    
  - name: SEO                  # High-value (needs 50+ karma)
    keywords: [AI search, GEO]
    max_daily_comments: 3
    min_karma: 50
```

The agent automatically skips subreddits you don't have enough karma for, and builds karma on easier ones first.

### Settings

Edit `~/.reddit-agent/.env`:

| Setting | Default | Description |
|---|---|---|
| `MAX_COMMENTS_PER_DAY` | 5 | Total daily limit |
| `MIN_COMMENT_INTERVAL_MINUTES` | 20 | Cooldown between posts |
| `QUALITY_THRESHOLD` | 7 | Min quality score (1-10) |

### Multiple Accounts

Create separate `.env` files and run with:

```bash
REDDIT_AGENT_ENV=~/.reddit-agent/.env.account2 reddit-agent
```

*(Multi-account rotation coming in v2)*

## Commands

```bash
reddit-agent              # Run one engagement cycle
reddit-agent --feedback   # Check past comments
reddit-agent --digest     # Performance report
```

## How It Works

```
Every 2 hours:
  1. Check account karma
  2. Pick subreddits matching karma level
  3. Browse subreddit feed (not search - more reliable)
  4. LLM evaluates each thread (is it worth commenting?)
  5. LLM generates a human-like comment
  6. LLM quality-checks the comment (naturalness, safety)
  7. Stealth browser types and posts the comment
  8. Verifies comment is visible (shadowban check)
  9. Logs everything to SQLite + learnings.md
  10. Next cycle uses learnings to improve
```

## Architecture

- **Python 3.12+** with Playwright for headless browsing
- **Any LLM** — auto-detects Anthropic or OpenAI from environment
- **SQLite** for persistent state (threads, comments, karma, learnings)
- **OpenClaw native** — installs as a skill with cron scheduling

## License

MIT
