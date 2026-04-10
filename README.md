# Reddit Agent

Autonomous Reddit engagement agent for [OpenClaw](https://openclaw.ai) and standalone use.

Runs on any machine (including headless VMs with no screen). Posts human-like comments on Reddit, builds karma on new accounts, learns from feedback, and improves over time.

## Why This Exists

Reddit is one of the most valuable platforms for organic engagement — posts get indexed by Google, cited by AI models (ChatGPT, Gemini, Perplexity), and drive real traffic. But:

- **Reddit's API is heavily restricted** — rate limits, pre-approval required, easy bot detection
- **Datacenter IPs are blocked** — VMs can't access Reddit normally
- **New accounts get auto-removed** — most subreddits require minimum karma
- **AI-sounding comments get flagged** — needs human-like writing
- **Manual posting doesn't scale** — you can't spend hours on Reddit every day

Reddit Agent solves all of these.

## What It Does

```
Every 2 hours (or on demand):
  1. Checks account karma → picks subreddits it can post in
  2. Browses subreddit feeds via stealth headless browser
  3. AI evaluates each thread for engagement opportunity
  4. AI generates a genuine, human-like comment
  5. AI quality-gates the comment (naturalness, safety, subtlety)
  6. Stealth browser types and posts with human-like delays
  7. Verifies comment is visible (shadowban detection)
  8. Tracks karma, learns from removals, improves next cycle
```

### Karma Building (New Accounts)

New accounts start with zero karma and get auto-removed from most subreddits. The agent handles this automatically:

1. **Phase 1** (0-20 karma): Posts genuine, helpful comments on open subreddits like r/AskReddit, r/NoStupidQuestions
2. **Phase 2** (20-50 karma): Unlocks medium-barrier subreddits like r/Entrepreneur, r/digital_marketing
3. **Phase 3** (50+ karma): Unlocks high-value subreddits like r/SEO, r/marketing

The agent detects your karma at the start of each cycle and automatically routes to the right subreddits.

### Anti-Detection

- Randomized browser fingerprints (user agent, viewport, timezone)
- Human-like typing delays (30-120ms per keystroke, variable)
- Randomized posting intervals (15-30 min between comments)
- Cookie-based authentication (bypasses datacenter IP blocks)
- No Reddit API usage (pure browser interaction)

### Learning Loop

After each cycle, the agent:
- Checks karma on past comments (what resonated?)
- Detects removed comments (what did mods flag?)
- Detects shadowbans (is the account compromised?)
- Writes learnings to a persistent file
- Uses learnings to generate better comments next time

## Install

### For OpenClaw Users

Tell your agent:

> "Install the Reddit agent from github.com/sohazur/reddit-agent"

The agent will handle everything. It will ask you for:
- Reddit username and password

That's it. No API keys needed (uses your OpenClaw's existing LLM). No Slack needed (reports through your chat).

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/sohazur/reddit-agent/main/install.sh | bash
```

### Manual Install

```bash
git clone https://github.com/sohazur/reddit-agent.git ~/.reddit-agent
cd ~/.reddit-agent
./install.sh
```

### Non-Interactive (for scripts)

```bash
REDDIT_USERNAME=myuser REDDIT_PASSWORD=mypass \
  ~/.reddit-agent/install.sh --non-interactive
```

## Updating

Updates pull the latest code from GitHub and reinstall:

```bash
reddit-agent-update
```

When you update the repo, everyone who runs `reddit-agent-update` gets the new features automatically.

## Cookie Setup (Required for VMs/Cloud)

Reddit blocks datacenter IPs aggressively. The agent uses your browser cookies to bypass this.

**One-time setup:**

1. Log in to Reddit on your phone or laptop browser
2. Install [Cookie-Editor](https://cookie-editor.com/) browser extension
3. Go to reddit.com, click the extension, export as JSON
4. Save to `~/.reddit-agent/data/cookies.json`

Cookies last weeks. The agent refreshes them automatically when possible.

## Configuration

### Subreddits

Edit `~/.reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  # Karma building (no requirements)
  - name: AskReddit
    max_daily_comments: 2
    min_karma: 0
    tone: "Casual, conversational."
    notes: "No karma requirement. Great for building karma."

  # High-value target (needs karma first)
  - name: SEO
    keywords: [AI search, GEO, llms.txt]
    max_daily_comments: 3
    min_karma: 50
    tone: "Technical, data-driven."
    notes: "Mods aggressive on self-promotion."
```

### Settings

Edit `~/.reddit-agent/.env`:

| Setting | Default | What it does |
|---|---|---|
| `MAX_COMMENTS_PER_DAY` | 5 | Daily posting limit across all subreddits |
| `MIN_COMMENT_INTERVAL_MINUTES` | 20 | Minimum gap between posts (randomized up) |
| `QUALITY_THRESHOLD` | 7 | Minimum AI quality score to post (1-10) |
| `CYCLE_INTERVAL_HOURS` | 2 | How often the cron runs |

### Multiple Accounts

For multiple accounts, create separate installs:

```bash
REDDIT_AGENT_DIR=~/.reddit-agent-2 \
REDDIT_USERNAME=account2 \
REDDIT_PASSWORD=pass2 \
  ~/.reddit-agent/install.sh --non-interactive
```

## Commands

| Command | What it does |
|---|---|
| `reddit-agent` | Run one full engagement cycle |
| `reddit-agent --feedback` | Check karma and removals on past comments |
| `reddit-agent --digest` | Print daily performance summary |
| `reddit-agent-update` | Pull latest code and update |

## How It Works (Technical)

### Architecture

```
┌─────────────────────────────────────────────────┐
│  Scheduler (OpenClaw cron / system cron)        │
│  Triggers every 2 hours                         │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Orchestrator (src/main.py)                     │
│  ├── Karma check → filter subreddits           │
│  ├── For each subreddit:                        │
│  │   ├── Intel report (community analysis)      │
│  │   ├── Browse feed → find threads             │
│  │   ├── Evaluate threads (LLM)                 │
│  │   ├── Generate comment (LLM)                 │
│  │   ├── Quality gate (LLM)                     │
│  │   └── Post via stealth browser               │
│  ├── Feedback loop (check past comments)        │
│  └── Update learnings                           │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Browser Layer (Playwright, headless)           │
│  ├── Stealth: fingerprint rotation, JS patches  │
│  ├── Cookie auth: bypass IP blocks              │
│  ├── Human typing: 30-120ms per keystroke       │
│  └── Shadowban check: incognito verification    │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Persistence (SQLite + files)                   │
│  ├── threads table: what we've seen             │
│  ├── comments table: what we've posted + karma  │
│  ├── subreddit_intel: community analysis        │
│  ├── learnings.md: what works and what doesn't  │
│  └── cookies.json: browser session              │
└─────────────────────────────────────────────────┘
```

### LLM Provider

The agent auto-detects which LLM API is available:
1. `ANTHROPIC_API_KEY` in environment → uses Claude
2. `OPENAI_API_KEY` in environment → uses GPT-4
3. Keys in `~/.bashrc` or `~/.profile` → reads from there
4. OpenClaw shell env → imported automatically

No manual API key configuration needed.

### File Structure

```
~/.reddit-agent/
├── .env                          # Reddit credentials + settings
├── data/
│   ├── subreddits.yaml           # Target subreddit config
│   ├── reddit.db                 # SQLite (threads, comments, karma)
│   ├── cookies.json              # Browser session cookies
│   ├── learnings.md              # What the agent has learned
│   └── subreddit_reports/        # Per-subreddit intelligence
├── prompts/                      # LLM prompt templates (editable)
├── src/                          # Python source code
└── tests/                        # Test suite
```

## OpenClaw Integration

When installed on an OpenClaw machine:

- **Skill** registered at `~/.openclaw/agents/skills/reddit-agent/`
- **Cron** runs every 2 hours
- **Heartbeat** tasks added for monitoring
- **Chat control**: "run the reddit agent", "how's reddit doing?", "add r/marketing"

The agent reports results through your OpenClaw chat (WhatsApp, Telegram, Discord — whatever you use).

## Safety & Ethics

- **Rate limited** — conservative posting cadence to avoid bans
- **Quality gated** — every comment scored before posting
- **No vote manipulation** — only comments, never upvotes/downvotes
- **No spam** — genuine, helpful comments that add value
- **Shadowban detection** — stops posting if account is compromised
- **Account karma respected** — doesn't post where it'll be auto-removed

## Contributing

PRs welcome. Key areas for contribution:

- [ ] Multi-account rotation with proxy support
- [ ] Auto cookie refresh when sessions expire
- [ ] ClawHub package for one-click OpenClaw install
- [ ] Web dashboard for monitoring
- [ ] More subreddit presets

## License

MIT — use it however you want.
