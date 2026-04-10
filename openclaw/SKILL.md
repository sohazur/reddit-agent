---
name: reddit-agent
description: "Autonomous Reddit engagement agent. Scans subreddits, evaluates threads, generates human-like comments, posts via browser, and learns from feedback. Commands: reddit-agent (run cycle), reddit-agent --feedback (check past comments), reddit-agent --digest (daily report)."
allowed-tools: Bash(reddit-agent *), Bash(cat ~/.reddit-agent/data/*), Bash(~/.reddit-agent/.venv/bin/python *), Read, Edit
---

# Reddit Agent — OpenClaw Skill

Autonomous Reddit engagement agent. Browser-based (no API needed). Learns from feedback.

## Install

```bash
# From the repo:
cd /path/to/reddit-agent && ./install.sh

# Or non-interactive (for agents):
REDDIT_USERNAME=myuser REDDIT_PASSWORD=mypass ANTHROPIC_API_KEY=sk-ant-... ./install.sh --non-interactive
```

## Commands

```bash
reddit-agent              # Run one engagement cycle
reddit-agent --feedback   # Check past comments for karma/removals
reddit-agent --digest     # Send daily Slack digest
```

## What It Does Per Cycle

1. **Scans** target subreddits for relevant threads (browser-based)
2. **Studies** subreddit culture (generates intelligence report)
3. **Evaluates** each thread (Claude API scores 0-10)
4. **Generates** human-like comment (Claude API with brand voice)
5. **Quality gates** the comment (naturalness, relevance, safety, subtlety)
6. **Posts** via stealth browser with human-like typing delays
7. **Verifies** comment is visible (shadowban detection)
8. **Learns** from feedback (karma, removals, mod actions)

## Configuration

Edit `~/.reddit-agent/.env`:
| Variable | Default | Description |
|---|---|---|
| MAX_COMMENTS_PER_DAY | 5 | Daily posting limit |
| MIN_COMMENT_INTERVAL_MINUTES | 20 | Cooldown between posts |
| QUALITY_THRESHOLD | 7 | Min quality score (1-10) |

Edit `~/.reddit-agent/data/subreddits.yaml` for target subreddits.

## Monitoring

| File | What |
|---|---|
| `data/learnings.md` | What the agent learned from feedback |
| `data/subreddit_reports/*.md` | Per-subreddit intelligence reports |
| `data/reddit.db` | Full SQLite history |
| `data/screenshots/` | Error screenshots |

## Safe Posting Cadence

- New accounts: 2-3 comments/day max
- Established (3-4 months): 10-20/day safe
- Min 15-minute spacing, randomized
- Per-subreddit limits enforced

## When to Use

Use this skill when the user asks to:
- Post on Reddit / engage with Reddit threads
- Check Reddit performance / karma / engagement
- Get a Reddit activity report
- Start/stop/configure the Reddit agent
- Add or remove target subreddits
