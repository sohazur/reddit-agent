# AGENTS.md — reddit-agent

Instructions for AI agents (Claude Code, OpenClaw, or any LLM agent) to install, configure, and operate reddit-agent. Read this file before doing anything with the Reddit agent.

## Quick Setup URL

If you're an AI agent and someone pointed you here, the full step-by-step install guide is at:
`https://raw.githubusercontent.com/sohazur/reddit-agent/main/INSTALL.md`

Fetch and follow that file. It tells you exactly what to ask the user and how to configure everything.

## What This Is

An autonomous Reddit engagement agent that posts human-like comments via a stealth headless browser. It builds karma on new accounts, learns from feedback, and improves over time. Runs on any machine including headless VMs.

## Installation

Install globally with npm:

```bash
npm i -g reddit-agent
```

Then set up credentials:

```bash
reddit-agent setup
```

This will ask for:
- **Reddit username** (required)
- **Reddit password** (required)
- **Max comments per day** (default: 5)

Nothing else is needed. The agent auto-detects LLM API keys from the environment.

### Non-Interactive Install (for agents)

```bash
npm i -g reddit-agent
REDDIT_USERNAME="<user>" REDDIT_PASSWORD="<pass>" reddit-agent setup --non-interactive
```

Or write the `.env` file directly:

```bash
# Find the install directory
INSTALL_DIR=$(npm root -g)/reddit-agent

cat > "$INSTALL_DIR/.env" << EOF
REDDIT_USERNAME=<username>
REDDIT_PASSWORD=<password>
MAX_COMMENTS_PER_DAY=5
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
EOF
```

### Cookie Setup (Required for VMs/Cloud Servers)

Reddit blocks datacenter IPs. If running on a VM, you need browser cookies from a real login.

**Ask the user:**
> "Reddit blocks cloud server IPs. I need your browser cookies to log in.
> Please log in to Reddit on your phone/laptop, install the Cookie-Editor
> browser extension, export cookies for reddit.com as JSON, and send them to me."

Save the cookies:
```bash
INSTALL_DIR=$(npm root -g)/reddit-agent
cat > "$INSTALL_DIR/data/cookies.json" << 'EOF'
<paste the JSON here>
EOF
```

## Commands

| Command | What it does |
|---|---|
| `reddit-agent run` | Run one full engagement cycle |
| `reddit-agent feedback` | Check karma and removals on past comments |
| `reddit-agent digest` | Print daily performance summary |
| `reddit-agent setup` | Interactive setup (credentials + environment) |
| `reddit-agent update` | Pull latest version |
| `reddit-agent status` | Show config and health check |
| `reddit-agent help` | Show all commands |

## Configuration

### Target Subreddits

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  - name: AskReddit         # For karma building
    max_daily_comments: 2
    min_karma: 0             # No requirement
    tone: "Casual, conversational."

  - name: SEO               # High-value target
    keywords: [AI search, GEO, llms.txt]
    max_daily_comments: 3
    min_karma: 50            # Needs karma first
    tone: "Technical, data-driven."
```

The agent **automatically skips** subreddits the account doesn't have enough karma for.

### Posting Settings

Edit `$(npm root -g)/reddit-agent/.env`:

| Setting | Default | Description |
|---|---|---|
| `MAX_COMMENTS_PER_DAY` | 5 | Daily limit |
| `MIN_COMMENT_INTERVAL_MINUTES` | 20 | Gap between posts |
| `QUALITY_THRESHOLD` | 7 | Minimum AI quality score |

## User Request Mapping

When the user asks for something, here's what to do:

| User says | Action |
|---|---|
| "Install the Reddit agent" | `npm i -g reddit-agent && reddit-agent setup` |
| "Run the Reddit bot" | `reddit-agent run` — report results |
| "How's Reddit doing?" | `reddit-agent digest` — summarize output |
| "Add r/marketing" | Edit `data/subreddits.yaml`, add the subreddit |
| "Post about AI tools" | Add keywords to relevant subreddit in yaml |
| "Post more often" | Increase `MAX_COMMENTS_PER_DAY` in `.env` |
| "Stop posting" | Set `MAX_COMMENTS_PER_DAY=0` |
| "Check for problems" | `reddit-agent feedback` — report issues |
| "What did it learn?" | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| "Update the agent" | `reddit-agent update` |
| "Use a different account" | Edit `REDDIT_USERNAME`/`REDDIT_PASSWORD` in `.env` |
| "Show me the config" | `reddit-agent status` |

## How It Works

1. **Karma check** — reads the account's karma from Reddit profile
2. **Subreddit filtering** — skips subs needing more karma than account has
3. **Karma building** — on low-karma accounts, posts genuine helpful comments on r/AskReddit etc.
4. **Brand mode** — once karma is high enough, targets brand-relevant subs with smart comments
5. **Quality gate** — every comment scored 1-10 for naturalness, relevance, safety, subtlety
6. **Stealth posting** — headless browser with fingerprint rotation, human typing delays
7. **Verification** — checks if comment is visible (shadowban detection)
8. **Learning** — tracks karma, removals, writes learnings for next cycle

## Monitoring

| What | How |
|---|---|
| Learnings | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| Subreddit intel | `cat $(npm root -g)/reddit-agent/data/subreddit_reports/*.md` |
| Error screenshots | `ls $(npm root -g)/reddit-agent/data/screenshots/` |
| Database | `$(npm root -g)/reddit-agent/.venv/bin/python -c "from src.db import get_daily_summary; import json; print(json.dumps(get_daily_summary(), indent=2))"` |

## OpenClaw Integration

When installed on an OpenClaw machine, the installer automatically:
- Registers as an OpenClaw skill
- Sets up a cron job (every 2 hours)
- Adds tasks to HEARTBEAT.md

The agent reports results through your OpenClaw chat channel.

## Updating

```bash
reddit-agent update
```

Or reinstall from npm:
```bash
npm i -g reddit-agent@latest
```

Updates include new features, bug fixes, and improved prompts. Config and data are preserved.
