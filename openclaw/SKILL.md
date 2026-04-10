---
name: reddit-agent
description: "Autonomous Reddit engagement agent. Stealth browser posting, karma building, shadowban detection, learning loop. Install: 'Install the Reddit agent from github.com/sohazur/reddit-agent'. Commands: reddit-agent, reddit-agent --feedback, reddit-agent --digest."
allowed-tools: Bash(reddit-agent *), Bash(cat ~/.reddit-agent/data/*), Bash(~/.reddit-agent/.venv/bin/python *), Bash(cd ~/.reddit-agent *), Bash(git clone *), Read, Edit
---

# Reddit Agent

Autonomous Reddit engagement on a headless VM. Stealth browser, karma building, learning loop.

## Installation (when user says "install the reddit agent")

**Step 1: Ask the user for credentials.** Only two things needed:

- Reddit username
- Reddit password

Do NOT ask for API keys (you already have LLM access), Slack webhooks (you ARE the notification channel), or anything else.

**Step 2: Run the installer:**

```bash
git clone https://github.com/sohazur/reddit-agent.git ~/.reddit-agent 2>/dev/null || (cd ~/.reddit-agent && git pull)
cd ~/.reddit-agent
REDDIT_USERNAME="<username>" REDDIT_PASSWORD="<password>" ./install.sh --non-interactive
```

**Step 3: Cookie setup.** The VM's IP is likely blocked by Reddit. Ask the user:

> "Reddit blocks datacenter IPs. I need your browser cookies to log in. Please:
> 1. Log in to Reddit on your phone/laptop
> 2. Install a cookie export extension (Cookie-Editor)
> 3. Export cookies for reddit.com as JSON
> 4. Send me the JSON"

Save the cookies:
```bash
cat > ~/.reddit-agent/data/cookies.json << 'EOF'
<paste the cookies JSON here>
EOF
```

**Step 4: Test it:**
```bash
reddit-agent --digest
```

**Step 5: Tell the user it's ready.** Report what subreddits are configured and when the first cycle will run.

## Running

```bash
reddit-agent              # Run one engagement cycle
reddit-agent --feedback   # Check karma on past comments
reddit-agent --digest     # Performance report
```

**IMPORTANT:** After running any command, report the results to the user in chat. You are the notification system.

## Configuration

**Add/remove subreddits:** Edit `~/.reddit-agent/data/subreddits.yaml`

**Change posting limits:** Edit `~/.reddit-agent/.env`
- `MAX_COMMENTS_PER_DAY` (default: 5)
- `MIN_COMMENT_INTERVAL_MINUTES` (default: 20)

**Set an objective:** Edit `~/.reddit-agent/data/subreddits.yaml` to add subreddits relevant to the user's objective. Each subreddit needs:
- `keywords`: topics to look for
- `tone`: how to write comments
- `notes`: community-specific rules
- `min_karma`: minimum karma needed (0 for karma-building subs)

## Monitoring

| What | How |
|---|---|
| Learnings | `cat ~/.reddit-agent/data/learnings.md` |
| Subreddit intel | `cat ~/.reddit-agent/data/subreddit_reports/*.md` |
| Daily stats | `reddit-agent --digest` |
| Errors | `ls ~/.reddit-agent/data/screenshots/` |

## User Requests Quick Reference

| User says | Do this |
|---|---|
| "Install the Reddit agent" | Run install flow above |
| "Run the Reddit bot" | `reddit-agent` then report |
| "How's Reddit doing?" | `reddit-agent --digest` |
| "Add r/marketing" | Edit subreddits.yaml |
| "Post about AI tools" | Add keywords to subreddits.yaml |
| "Post more/less" | Edit MAX_COMMENTS_PER_DAY in .env |
| "Stop posting" | Set MAX_COMMENTS_PER_DAY=0 |
| "Check for problems" | `reddit-agent --feedback` |
| "What did it learn?" | `cat ~/.reddit-agent/data/learnings.md` |
| "Use a different account" | Edit REDDIT_USERNAME/PASSWORD in .env |

## How It Works

1. **Karma check** — reads account profile, skips subs needing more karma
2. **Karma building** — posts genuine helpful comments on AskReddit etc. to build karma
3. **Brand mode** — once karma is high enough, targets brand-relevant subs (SEO, marketing)
4. **Stealth** — randomized browser fingerprints, human typing delays, cookie-based auth
5. **Quality gate** — every comment scored for naturalness/safety before posting
6. **Learning** — tracks karma, removals, writes learnings for next cycle
7. **Shadowban detection** — checks if comments are visible in incognito
