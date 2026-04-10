# reddit-agent

Autonomous Reddit engagement agent. One command to install, works with any AI agent or standalone.

```bash
npm i -g reddit-agent
reddit-agent setup
```

## What It Does

Runs every 2 hours (or on demand) and:

1. **Browses** target subreddits via a stealth headless browser
2. **Evaluates** threads for engagement opportunity using AI
3. **Generates** human-like comments (not AI-sounding corporate speak)
4. **Quality-checks** every comment before posting (naturalness, safety, subtlety)
5. **Posts** via browser with human-like typing delays
6. **Learns** from karma, removals, and shadowbans to improve over time

### Handles the Hard Parts

| Problem | How reddit-agent solves it |
|---|---|
| Reddit API restrictions | No API used — pure browser interaction |
| Datacenter IPs blocked | Cookie-based auth from your real browser |
| New accounts get auto-removed | Auto-builds karma on easy subreddits first |
| AI comments sound robotic | Quality gate scores naturalness before posting |
| Manual posting doesn't scale | Runs autonomously every 2 hours |
| No memory between sessions | SQLite DB + learnings file persist across runs |
| Shadowbans go undetected | Incognito re-check after every post |

## Install

### npm (recommended)

```bash
npm i -g reddit-agent
reddit-agent setup
```

Setup asks for your Reddit username and password. That's it.

### From GitHub

```bash
npm i -g github:sohazur/reddit-agent
reddit-agent setup
```

### For AI Agents (OpenClaw, Claude Code, etc.)

Tell your agent:

> "Install reddit-agent: `npm i -g reddit-agent && reddit-agent setup`"

The agent reads `AGENTS.md` in the package for full instructions on how to configure and operate it. See [AGENTS.md](AGENTS.md) for the complete agent playbook.

### Non-Interactive (scripts, CI, agents)

```bash
npm i -g reddit-agent
# Write config directly
INSTALL_DIR=$(npm root -g)/reddit-agent
cat > "$INSTALL_DIR/.env" << EOF
REDDIT_USERNAME=your_username
REDDIT_PASSWORD=your_password
MAX_COMMENTS_PER_DAY=5
EOF
```

## First Run

On first `reddit-agent run`, the agent automatically:
1. Sets up a Python virtual environment
2. Installs dependencies (Playwright, AI SDKs)
3. Downloads a headless Chromium browser
4. Initializes the database

This takes 1-2 minutes on first run. Subsequent runs start in seconds.

## Cookie Setup (VMs / Cloud Servers)

Reddit blocks datacenter IPs. If running on a cloud server or VM:

1. Log in to Reddit on your phone or laptop
2. Install [Cookie-Editor](https://cookie-editor.com/) browser extension
3. Export cookies for reddit.com as JSON
4. Save to `$(npm root -g)/reddit-agent/data/cookies.json`

On a personal computer with a regular IP, this step is not needed.

## Configuration

### Target Subreddits

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  # Easy subreddits for building karma (no requirements)
  - name: AskReddit
    max_daily_comments: 2
    min_karma: 0
    tone: "Casual, short, relatable."

  # Your target subreddit (needs karma first)  
  - name: your_niche_subreddit
    keywords: [your, relevant, topics]
    max_daily_comments: 3
    min_karma: 50
    tone: "Match the community style."
    notes: "Any special rules for this community."
```

The agent **automatically skips** subreddits your account doesn't have enough karma for, and builds karma on easier subs first.

### Posting Limits

Edit `$(npm root -g)/reddit-agent/.env`:

| Setting | Default | What it does |
|---|---|---|
| `MAX_COMMENTS_PER_DAY` | 5 | Total daily comment limit |
| `MIN_COMMENT_INTERVAL_MINUTES` | 20 | Minimum gap between posts |
| `QUALITY_THRESHOLD` | 7 | Minimum AI quality score (1-10) |

### AI Provider

The agent auto-detects your AI provider from the environment:

| Priority | What it checks |
|---|---|
| 1st | `ANTHROPIC_API_KEY` environment variable → uses Claude |
| 2nd | `OPENAI_API_KEY` environment variable → uses GPT |
| 3rd | Keys in `~/.bashrc` or `~/.profile` |
| 4th | OpenClaw shell environment (auto-injected) |

**No API key?** If you're using this through an AI agent (OpenClaw, Claude Code), the agent's own LLM handles the intelligence. You don't need a separate key.

**Running standalone without any agent?** You need either an Anthropic or OpenAI API key in your environment.

## Commands

| Command | What it does |
|---|---|
| `reddit-agent setup` | Interactive setup (credentials + environment) |
| `reddit-agent run` | Run one engagement cycle |
| `reddit-agent feedback` | Check karma and removals on past comments |
| `reddit-agent digest` | Print performance summary |
| `reddit-agent update` | Pull latest version |
| `reddit-agent status` | Show config and health |
| `reddit-agent help` | Show all commands |

## How It Works

```
┌─────────────────────────────────────────────┐
│  Scheduler (cron / manual / agent trigger)  │
└──────────────────┬──────────────────────────┘
                   ▼
│  1. Check account karma                     │
│  2. Pick subreddits matching karma level    │
│  3. Browse subreddit feed                   │
│  4. AI evaluates each thread                │
│  5. AI generates a comment                  │
│  6. AI quality-checks (natural? safe?)      │
│  7. Stealth browser posts the comment       │
│  8. Verify it's visible (shadowban check)   │
│  9. Log to database + update learnings      │
└─────────────────────────────────────────────┘
```

### Karma Building

New Reddit accounts have zero karma and get auto-removed from most subreddits. The agent handles this:

- **Phase 1** (0-20 karma): Posts genuine helpful answers on r/AskReddit, r/NoStupidQuestions
- **Phase 2** (20-50 karma): Unlocks medium subreddits like r/Entrepreneur
- **Phase 3** (50+ karma): Unlocks competitive subreddits like r/SEO, r/marketing

Fully automatic. The agent checks karma at the start of each cycle.

### Anti-Detection

- Randomized browser fingerprints (user agent, viewport, timezone)
- Human-like typing (30-120ms per keystroke, variable speed)
- Randomized posting intervals (15-30 min gaps)
- Cookie-based auth (no API, no automation flags)
- Shadowban detection after every post

### Learning Loop

The agent writes what it learns to `data/learnings.md`:

```markdown
## 2026-04-10 — r/SEO
- Comment on 'AI overviews' thread got +12 karma. Technical tone worked.
- Comment on 'best tools' thread removed by mod. Too promotional.
- Lesson: r/SEO mods flag tool recommendations. Be more subtle.
```

This file is fed into future comment generation, so the agent literally gets smarter over time.

## AI Agent Integration

### OpenClaw

When installed on an OpenClaw machine, the agent automatically:
- Registers as an OpenClaw skill
- Sets up a cron job (every 2 hours)
- Reports results through your chat (WhatsApp, Telegram, etc.)

### Claude Code

Claude Code reads `AGENTS.md` automatically. Just say:
> "Run the Reddit agent"

### Any AI Agent

The `AGENTS.md` file in the package root contains complete instructions for any AI agent to install, configure, and operate reddit-agent.

## Updating

```bash
reddit-agent update
```

Or reinstall:
```bash
npm i -g reddit-agent@latest
```

When the package is updated, `reddit-agent update` pulls the new code. Your config, data, and learnings are preserved.

## Requirements

- **Node.js 18+** (for the CLI wrapper)
- **Python 3.12+** (auto-bootstrapped on first run)
- **2GB RAM** (for headless Chromium)
- An AI API key (Anthropic or OpenAI) OR an AI agent that provides LLM access

## License

MIT
