# Deploying the Reddit Agent

The agent is a pip-installed CLI driven on a schedule. In production a small
**heartbeat** fires periodically; the tool's own `--status` decides whether each
tick runs a cycle. Most ticks are no-ops — that's by design (it respects the
cycle interval, daily quota, and circuit breaker).

There is no daemon. There is no container required. Just an always-on box, a
schedule, real Reddit cookies, and an LLM key.

```
  cron / systemd timer / launchd  ──fires every 30 min──▶  deploy/heartbeat.sh
                                                                │
                                          reddit-agent --status │ (should I run?)
                                                                ▼
                                   paused? ──yes──▶ stop, log, alert (manual --resume)
                                      │no
                                   should_run? ──yes──▶ reddit-agent  (one cycle)
                                      │no
                                   do nothing this tick
```

## Prerequisites

1. **An always-on machine** — a Linux VPS, or a Mac that stays awake.
2. **Reddit cookies.** Reddit blocks datacenter IPs, so on a VPS you cannot just
   log in with username/password — you must supply cookies exported from a real
   browser:
   - Log in to Reddit in a normal browser on your laptop/phone.
   - Use the "Cookie-Editor" extension → export reddit.com cookies as JSON.
   - Save them to `~/.reddit-agent/data/cookies.json` on the box.
   - On your own Mac at home (residential IP), username/password login also works.
3. **An LLM key** — `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) in `.env`.

## Install

```bash
# On the box:
git clone https://github.com/sohazur/reddit-agent.git ~/.reddit-agent
cd ~/.reddit-agent
./install.sh
cp .env.example .env      # then edit .env (see below)
chmod +x deploy/heartbeat.sh
```

Minimum `.env` for production:

```bash
REDDIT_USERNAME=...
REDDIT_PASSWORD=...
ANTHROPIC_API_KEY=sk-ant-...
REDDIT_AGENT_OBJECTIVE="promote my SaaS to developers without being pushy"
REDDIT_AGENT_DOMAIN="technical SEO, site speed"

# Start conservative for the first week:
DRY_RUN=true               # flip to false only after dry-run looks good
MAX_COMMENTS_PER_DAY=2
MIN_COMMENT_INTERVAL_MINUTES=60
CYCLE_INTERVAL_HOURS=2

SLACK_WEBHOOK_URL=...       # optional but recommended for alerts
```

## Pre-flight (do NOT skip)

```bash
cd ~/.reddit-agent
.venv/bin/pytest -q            # 1. logic green
reddit-agent --status          # 2. config loads, returns JSON
DRY_RUN=true reddit-agent      # 3. dry-run: read the WOULD-POST lines
```

Only when the dry-run output looks right, set `DRY_RUN=false` and schedule it.

## Schedule it

### Option A — Linux (systemd timer)

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/reddit-agent.service ~/.config/systemd/user/
cp deploy/systemd/reddit-agent.timer   ~/.config/systemd/user/
# Edit the .service: set ExecStart / REDDIT_AGENT_DIR to your actual paths.
systemctl --user daemon-reload
systemctl --user enable --now reddit-agent.timer
loginctl enable-linger "$USER"     # keep the user timer running after logout

# Watch it:
systemctl --user list-timers reddit-agent.timer
journalctl --user -u reddit-agent.service -f
```

### Option B — Linux (plain cron)

```cron
# every 30 minutes
*/30 * * * * REDDIT_AGENT_DIR=$HOME/.reddit-agent $HOME/.reddit-agent/deploy/heartbeat.sh >> $HOME/.reddit-agent/data/heartbeat.log 2>&1
```

### Option C — macOS (launchd)

```bash
cp deploy/launchd/com.reddit-agent.heartbeat.plist ~/Library/LaunchAgents/
# Edit the plist: replace /Users/YOU with your home path.
launchctl load ~/Library/LaunchAgents/com.reddit-agent.heartbeat.plist
tail -f ~/.reddit-agent/data/heartbeat.log
```

## Operating it

```bash
reddit-agent --status     # what's it doing? should it run? any alerts?
reddit-agent --feedback   # check karma/removals on past comments (no posting)
reddit-agent --digest     # daily summary (also auto-sent once/day by heartbeat)
reddit-agent --resume     # clear the circuit breaker after you've investigated
```

When the breaker trips (shadowban, removal spike, repeated rule violations) the
heartbeat stops running cycles and logs the reason. Nothing resumes until you run
`--resume`. That is the safety design — leave it paused until you know why.

## Updating a deployed instance

```bash
cd ~/.reddit-agent
git fetch origin
git checkout main && git pull          # after the PR is merged
.venv/bin/pip install -e .             # if deps changed
.venv/bin/pytest -q                    # confirm green on the box
# The DB auto-migrates on init (e.g. the tier column) — no manual step.
```

## Rollback

The agent keeps no destructive state; rolling back is just checking out an
earlier commit and restarting the timer:

```bash
cd ~/.reddit-agent
git log --oneline -5
git checkout <previous-good-commit>
.venv/bin/pip install -e .
systemctl --user restart reddit-agent.timer   # or reload launchd / leave cron
```

The SQLite schema is additive (new columns have defaults), so an older build
reads a newer DB fine. To fully stop the agent: `systemctl --user disable --now
reddit-agent.timer` (or `launchctl unload ...`, or remove the cron line).
