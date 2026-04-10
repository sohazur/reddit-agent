# Reddit Agent

Autonomous Reddit engagement agent. Browser-based (no API restrictions). Learns from feedback.

Uses **browser-use + Claude API** hybrid architecture: browser-use handles the mechanical browser interaction, Claude handles the intelligence (evaluating threads, generating comments, quality scoring).

## Quick Install

```bash
git clone https://github.com/sohazur/reddit-agent.git
cd reddit-agent
./install.sh
```

The installer will:
1. Check prerequisites (Python 3.12+, uv/pip)
2. Install dependencies + Chromium
3. Ask for your Reddit credentials and Anthropic API key
4. Initialize the database
5. Run a health check
6. If OpenClaw is detected, install as a skill + set up cron

### Non-interactive install (for agents/VMs)

```bash
REDDIT_USERNAME=myuser \
REDDIT_PASSWORD=mypass \
ANTHROPIC_API_KEY=sk-ant-... \
./install.sh --non-interactive
```

## Usage

```bash
reddit-agent              # Run one engagement cycle
reddit-agent --feedback   # Check past comments
reddit-agent --digest     # Send daily Slack digest
```

## How It Works

Each cycle:
1. Scans target subreddits for relevant threads
2. Generates a subreddit intelligence report (culture, tone, hot topics)
3. Evaluates each thread's engagement opportunity (0-10 score)
4. Generates a human-like comment using brand voice + learnings
5. Quality-gates the comment (naturalness, relevance, safety, subtlety)
6. Posts via stealth headless browser with human-like timing
7. Verifies comment visibility (shadowban detection)
8. Learns from feedback (karma, removals, mod actions)

## Configuration

After install, edit `~/.reddit-agent/.env` for credentials and cadence settings.

Edit `~/.reddit-agent/data/subreddits.yaml` to configure target subreddits:

```yaml
subreddits:
  - name: SEO
    keywords: [AI search, GEO optimization]
    max_daily_comments: 3
    tone: "Technical, data-driven."
    notes: "Mods aggressive on self-promotion."
```

## OpenClaw Integration

If OpenClaw is installed, the installer automatically:
- Creates a skill at `~/.openclaw/skills/reddit-agent/`
- Registers a cron job to run every N hours
- Your OpenClaw agent can then run `reddit-agent` as a command

Add to your `HEARTBEAT.md`:
```markdown
## Reddit Agent
- [ ] Run reddit-agent cycle if last run was >2h ago
- [ ] Check reddit-agent --feedback for past comment performance
```

## Architecture

```
Scheduler (cron/OpenClaw) → Orchestrator → Scanner → Evaluator → Generator → Quality Gate → Browser → Feedback Loop
                                                        ↓                         ↓                       ↓
                                                   Claude API              Claude API              Shadowban Check
                                                                                                        ↓
                                                                                                  Learning Memory
```

## Requirements

- Python 3.12+
- Anthropic API key (for Claude)
- Reddit account (no 2FA)
- ~2GB RAM for Chromium
