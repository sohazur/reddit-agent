# reddit-agent

Autonomous Reddit engagement agent. One command to install. Works standalone, with [OpenClaw](https://openclaw.ai), or [Claude Code](https://claude.ai/code).

```bash
npm i -g reddit-agent
reddit-agent setup
```

## What It Does

Runs on autopilot and engages on Reddit like a real user:

- **Comments** on relevant threads with human-like responses
- **Upvotes** posts for natural account activity
- **Replies** to people who respond to your comments
- **Reads DMs** and replies intelligently
- **Finds leads** by spotting people asking for help and optionally DMs them
- **Creates posts** in subreddits (optional, off by default)
- **Browses** subreddits naturally (scrolls, reads, clicks)
- **Builds karma** automatically on new accounts
- **Learns** from what gets upvoted/removed and improves over time
- **Detects bans** by checking inbox before every cycle and auto-disabling banned subs
- **Detects shadowbans** by checking comment visibility in incognito

### Anti-Detection

Reddit actively bans AI-generated content. This agent is designed to avoid detection:

- Comments are written in casual internet style (lowercase, slang, short)
- Quality gate checks every comment against 10 known AI-detection patterns
- Human-like typing delays (30-120ms per keystroke, variable)
- Randomized browser fingerprints (user agent, viewport, timezone)
- Randomized posting intervals (15-30 min gaps)
- No Reddit API used — pure browser interaction

### Objective-Driven

During setup you define your goal (e.g., "promote my SaaS to developers" or "build authority in SEO"). The agent uses this objective to decide which threads are relevant and what angle to take in comments — without ever being explicitly promotional.

## Install

### npm (recommended)

```bash
npm i -g reddit-agent
reddit-agent setup
```

Setup asks for:
1. Reddit username and password (password is masked)
2. Your objective/goal
3. API key (Anthropic or OpenAI — auto-detected if already in your environment)
4. Posting limits
5. Whether to enable original posts and DM outreach

### For AI Agents

Tell your OpenClaw, Claude Code, or any AI agent:

> "Set up Reddit automation for me. Follow the instructions at https://raw.githubusercontent.com/sohazur/reddit-agent/main/INSTALL.md"

The agent reads `INSTALL.md`, installs the package, asks you a few questions, and configures everything. See [AGENTS.md](AGENTS.md) for the full agent playbook.

### From GitHub

```bash
npm i -g github:sohazur/reddit-agent
reddit-agent setup
```

## Cookie Setup

Reddit blocks headless browsers. After running `reddit-agent setup`, you need to export cookies from your real browser:

1. Log in to Reddit in Chrome/Firefox as your bot account
2. Install [Cookie-Editor](https://cookie-editor.com) extension
3. Go to reddit.com, click the extension, **Export as JSON**
4. Save to: `$(npm root -g)/reddit-agent/data/cookies.json`

The setup command shows the exact path after it finishes. This is a one-time step — cookies last for weeks.

## Configuration

### Objective

Your objective shapes everything — which threads get picked, what comments say, which DMs get sent. Set it during setup or change it anytime:

```bash
reddit-agent objective "promote my SaaS to developers without being pushy"
```

### Subreddits

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  # Easy subs for building karma first
  - name: AskReddit
    max_daily_comments: 2
    min_karma: 0
    tone: "casual, one-liners, be funny or relatable"

  # Your target sub (needs karma first)
  - name: SaaS
    keywords: [AI tools, automation, growth]
    max_daily_comments: 2
    min_karma: 30
    tone: "founder-to-founder, share real experience"
```

The agent auto-skips subreddits your account doesn't have enough karma for.

### Engagement Modes

All configurable in `.env`:

| Mode | Default | What |
|---|---|---|
| `ENGAGE_COMMENT` | on | Comment on threads |
| `ENGAGE_UPVOTE` | on | Upvote posts for natural activity |
| `ENGAGE_REPLY` | on | Reply when people respond to you |
| `ENGAGE_BROWSE` | on | Scroll subreddits like a real user |
| `ENGAGE_DM_REPLY` | on | Reply to incoming DMs |
| `ENGAGE_POST` | **off** | Create original text posts |
| `ENGAGE_DM_OUTREACH` | **off** | Proactively DM people asking for help |

### Posting Limits

| Setting | Default | What |
|---|---|---|
| `MAX_COMMENTS_PER_DAY` | 5 | Total daily limit |
| `MIN_COMMENT_INTERVAL_MINUTES` | 20 | Gap between posts |
| `QUALITY_THRESHOLD` | 7 | Min AI quality score (1-10) |

### AI Provider

Auto-detected. No config needed if you have one of these in your environment:

- `ANTHROPIC_API_KEY` → uses Claude
- `OPENAI_API_KEY` → uses GPT

Setup asks for a key if none is found. OpenClaw users can skip — the agent uses OpenClaw's LLM.

Override the model: `REDDIT_AGENT_MODEL=gpt-4o` in `.env`

## Commands

| Command | What |
|---|---|
| `reddit-agent setup` | Interactive setup |
| `reddit-agent run` | Run one engagement cycle |
| `reddit-agent feedback` | Check karma and removals |
| `reddit-agent digest` | Performance summary |
| `reddit-agent objective "new goal"` | Change objective |
| `reddit-agent status` | Config and health check |
| `reddit-agent update` | Pull latest version |
| `reddit-agent setup-password` | Update password securely |

## How It Works

Each cycle (every 2 hours or on demand):

```
1. Check inbox        → detect bans, auto-disable banned subs
2. Check karma        → filter subs by account karma level
3. Browse             → scroll subs naturally
4. Comment            → find threads → evaluate → generate → quality-check → post
5. Upvote             → upvote a few posts per sub
6. Reply              → respond to people who replied to us
7. DM replies         → read and reply to incoming DMs
8. DM outreach        → find people asking for help, DM them (if enabled)
9. Feedback           → check karma on past comments, detect removals
10. Learn             → write what worked/didn't for next cycle
```

### Karma Building

New accounts start by posting in easy subs (r/AskReddit, r/NoStupidQuestions). Once karma reaches the threshold, the agent unlocks your target subs automatically.

### Lead Tracking

When DMs come in from people related to your objective, or when outreach DMs are sent, leads are saved to `data/leads.json` for your review.

### Learning

The agent writes what it learns to `data/learnings.md` — which comments got upvoted, which got removed, what mod patterns to avoid. This file is fed into future comment generation.

## Monitoring

| What | Command |
|---|---|
| Performance | `reddit-agent digest` |
| Learnings | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| Subreddit intel | `cat $(npm root -g)/reddit-agent/data/subreddit_reports/*.md` |
| Leads | `cat $(npm root -g)/reddit-agent/data/leads.json` |
| Errors | `ls $(npm root -g)/reddit-agent/data/screenshots/` |

## Updating

```bash
reddit-agent update
```

Or: `npm i -g reddit-agent@latest`

Updates include new features, better prompts, and bug fixes. Config and data are preserved.

## Requirements

- Node.js 18+
- Python 3.12+ (auto-installed on first run)
- ~2GB RAM (for headless Chromium)
- An Anthropic or OpenAI API key (or an AI agent that provides LLM access)

## License

MIT
