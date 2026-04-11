# AGENTS.md — reddit-agent

Instructions for AI agents (Claude Code, OpenClaw, or any LLM agent) to install, configure, and operate reddit-agent.

## Quick Setup URL

If someone pointed you here, fetch and follow:
`https://raw.githubusercontent.com/sohazur/reddit-agent/main/INSTALL.md`

That file has the complete step-by-step setup flow.

## What This Is

An autonomous Reddit engagement agent that behaves like a real user — comments, upvotes, replies to DMs, browses, and learns from feedback. Designed to avoid AI detection by writing in casual internet style.

Key capabilities:
- Comments on relevant threads (casual style, not AI-sounding)
- Upvotes, browses, replies — full user behavior
- Reads and replies to DMs, finds outreach leads
- Builds karma on new accounts automatically
- Detects bans and shadowbans, stops posting when caught
- Learns from feedback and improves over time
- Objective-driven: user sets their goal, agent adapts

## Installation

```bash
npm i -g reddit-agent
reddit-agent setup
```

Setup asks for:
1. **Reddit username** (safe to share in chat)
2. **Reddit password** (masked input — never shown in chat)
3. **Objective** ("promote my SaaS to developers", "build authority in fitness", etc.)
4. **API key** (Anthropic or OpenAI — asked only if none detected in env)
5. **Max comments/day** (default 5)
6. **Create original posts?** (y/n, default n)
7. **DM outreach?** (y/n, default n)

### Handling Passwords Securely

**DO NOT ask for passwords in chat.** The setup command handles credentials locally:

```bash
reddit-agent setup
```

If the user is remote (WhatsApp/Telegram), have them SSH in or use:
```bash
reddit-agent setup-password
```

### Non-Interactive (for scripts)

```bash
INSTALL_DIR=$(npm root -g)/reddit-agent
cat > "$INSTALL_DIR/.env" << EOF
REDDIT_USERNAME=<username>
REDDIT_PASSWORD=<password>
REDDIT_AGENT_OBJECTIVE=<their goal>
OPENAI_API_KEY=<key if needed>
MAX_COMMENTS_PER_DAY=5
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
ENGAGE_COMMENT=true
ENGAGE_UPVOTE=true
ENGAGE_REPLY=true
ENGAGE_POST=false
ENGAGE_BROWSE=true
ENGAGE_DM_REPLY=true
ENGAGE_DM_OUTREACH=false
EOF
chmod 600 "$INSTALL_DIR/.env"
```

### Cookie Setup

After install, if on a VM or cloud server, cookies are needed:

```bash
# Check if cookies exist
ls $(npm root -g)/reddit-agent/data/cookies.json
```

If missing, ask the user to export from their browser. See INSTALL.md for details.

## Commands

| Command | What |
|---|---|
| `reddit-agent run` | Run one full cycle |
| `reddit-agent feedback` | Check past comments |
| `reddit-agent digest` | Performance summary |
| `reddit-agent objective "new goal"` | Change objective |
| `reddit-agent status` | Config and health |
| `reddit-agent update` | Get latest version |
| `reddit-agent setup` | Full interactive setup |
| `reddit-agent setup-password` | Update password only |

## User Request Mapping

| User says | Action |
|---|---|
| "Install the Reddit agent" | `npm i -g reddit-agent && reddit-agent setup` |
| "Run the Reddit bot" | `reddit-agent run` → report results |
| "How's Reddit going?" | `reddit-agent digest` → summarize |
| "Add r/marketing" | Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml` |
| "Change my objective" | `reddit-agent objective "new goal"` |
| "Post more/less" | Edit `MAX_COMMENTS_PER_DAY` in `.env` |
| "Stop posting" | Set `MAX_COMMENTS_PER_DAY=0` |
| "Enable DM outreach" | Set `ENGAGE_DM_OUTREACH=true` in `.env` |
| "Enable original posts" | Set `ENGAGE_POST=true` in `.env` |
| "Check for problems" | `reddit-agent feedback` → report |
| "What did it learn?" | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| "Show me leads" | `cat $(npm root -g)/reddit-agent/data/leads.json` |
| "Update the agent" | `reddit-agent update` |

## Subreddit Configuration

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`:

```yaml
subreddits:
  - name: SubredditName
    keywords: [topic1, topic2]
    max_daily_comments: 2
    min_karma: 0           # 0 = karma building, 20-50 = needs karma
    tone: "casual, match the community"
    notes: "any rules to follow"
```

When the user gives an objective, create subreddits that match:
- 2-3 karma-building subs (min_karma: 0)
- 2-4 target subs relevant to their goal (min_karma: 20-50)

## Monitoring

| What | How |
|---|---|
| Performance | `reddit-agent digest` |
| Learnings | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| Subreddit intel | `cat $(npm root -g)/reddit-agent/data/subreddit_reports/*.md` |
| Leads | `cat $(npm root -g)/reddit-agent/data/leads.json` |
| Errors | `ls $(npm root -g)/reddit-agent/data/screenshots/` |

## How It Works

Each cycle:
1. Inbox check → detect bans, auto-disable banned subs
2. Karma check → skip subs needing more karma
3. Browse subs → scroll naturally
4. Comment → evaluate thread → generate casual comment → quality-check for AI tells → post
5. Upvote → a few posts per sub
6. Reply → respond to people who replied to us
7. DM → reply to incoming, optionally DM outreach
8. Feedback → check past comment karma, detect removals
9. Learn → write learnings for next cycle

## OpenClaw Integration

On OpenClaw machines, the installer automatically registers:
- A skill at `~/.openclaw/agents/skills/reddit-agent/`
- A cron job (every 2 hours)
- HEARTBEAT.md tasks

The agent reports results through your chat channel.
