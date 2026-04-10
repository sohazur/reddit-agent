#!/usr/bin/env bash
set -euo pipefail

# Reddit Agent — One-command installer
# Usage: curl -fsSL <repo-url>/install.sh | bash
#   or:  ./install.sh
#   or:  ./install.sh --non-interactive (uses env vars)

INSTALL_DIR="${REDDIT_AGENT_DIR:-$HOME/.reddit-agent}"
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; }
ask()   { echo -en "${BOLD}$*${NC} "; }

# ─── Step 0: Check prerequisites ───────────────────────────────

echo ""
echo -e "${BOLD}Reddit Agent — Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Python 3.12+
if ! command -v python3 &>/dev/null; then
    err "Python 3 not found. Install Python 3.12+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    err "Python $PY_VERSION found, but 3.12+ is required."
    exit 1
fi
info "Python $PY_VERSION"

# Check uv (or pip)
if command -v uv &>/dev/null; then
    PKG_MGR="uv"
    info "uv package manager found"
elif command -v pip3 &>/dev/null; then
    PKG_MGR="pip"
    info "pip found (uv recommended for speed: curl -LsSf https://astral.sh/uv/install.sh | sh)"
else
    err "Neither uv nor pip found. Install one first."
    exit 1
fi

# ─── Step 1: Install the project ───────────────────────────────

if [ -d "$INSTALL_DIR" ]; then
    warn "Existing installation found at $INSTALL_DIR"
    if [ "${1:-}" != "--non-interactive" ]; then
        ask "Overwrite? [y/N]:"
        read -r OVERWRITE
        if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
            echo "Aborted."
            exit 0
        fi
    fi
    rm -rf "$INSTALL_DIR"
fi

echo ""
info "Installing to $INSTALL_DIR"

# Clone or copy
if [ -d "$(dirname "$0")/src" ] && [ -f "$(dirname "$0")/pyproject.toml" ]; then
    # Running from local repo
    cp -r "$(dirname "$0")" "$INSTALL_DIR"
    info "Copied from local directory"
else
    # Clone from GitHub
    if command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/sohazur/reddit-agent.git "$INSTALL_DIR" 2>/dev/null || {
            err "Failed to clone repo. Copy the project manually to $INSTALL_DIR"
            exit 1
        }
        info "Cloned from GitHub"
    else
        err "git not found. Clone the repo manually to $INSTALL_DIR"
        exit 1
    fi
fi

cd "$INSTALL_DIR"

# Create venv and install deps
if [ "$PKG_MGR" = "uv" ]; then
    uv venv .venv --quiet 2>/dev/null
    uv pip install -e ".[dev]" --quiet 2>/dev/null
else
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]" --quiet 2>/dev/null
fi
info "Dependencies installed"

# Install Playwright + Chromium
.venv/bin/playwright install chromium --quiet 2>/dev/null || .venv/bin/playwright install chromium 2>/dev/null
info "Chromium browser installed"

# ─── Step 2: Collect credentials ───────────────────────────────

echo ""
echo -e "${BOLD}Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ENV_FILE="$INSTALL_DIR/.env"

if [ "${1:-}" = "--non-interactive" ]; then
    # Use env vars directly
    if [ -z "${REDDIT_USERNAME:-}" ] || [ -z "${REDDIT_PASSWORD:-}" ] || [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        err "Non-interactive mode requires REDDIT_USERNAME, REDDIT_PASSWORD, ANTHROPIC_API_KEY env vars"
        exit 1
    fi
    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=$REDDIT_USERNAME
REDDIT_PASSWORD=$REDDIT_PASSWORD
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-}
MAX_COMMENTS_PER_DAY=${MAX_COMMENTS_PER_DAY:-5}
MIN_COMMENT_INTERVAL_MINUTES=${MIN_COMMENT_INTERVAL_MINUTES:-20}
QUALITY_THRESHOLD=${QUALITY_THRESHOLD:-7}
CYCLE_INTERVAL_HOURS=${CYCLE_INTERVAL_HOURS:-2}
LOG_LEVEL=${LOG_LEVEL:-INFO}
SCREENSHOT_ON_ERROR=true
EOF
else
    echo "I need a few things to get started:"
    echo ""

    # Reddit credentials
    ask "Reddit username:"
    read -r R_USER
    ask "Reddit password:"
    read -rs R_PASS
    echo ""

    # Anthropic API key
    ask "Anthropic API key (sk-ant-...):"
    read -rs A_KEY
    echo ""

    # Slack (optional)
    echo ""
    ask "Slack webhook URL (optional, press Enter to skip):"
    read -r S_WEBHOOK

    # Posting cadence
    echo ""
    echo "Posting cadence (press Enter for defaults):"
    ask "Max comments per day [5]:"
    read -r MAX_DAILY
    MAX_DAILY="${MAX_DAILY:-5}"

    ask "Min minutes between comments [20]:"
    read -r MIN_INTERVAL
    MIN_INTERVAL="${MIN_INTERVAL:-20}"

    ask "Quality threshold 1-10 [7]:"
    read -r QUALITY
    QUALITY="${QUALITY:-7}"

    ask "Cycle interval in hours [2]:"
    read -r CYCLE_HRS
    CYCLE_HRS="${CYCLE_HRS:-2}"

    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=$R_USER
REDDIT_PASSWORD=$R_PASS
ANTHROPIC_API_KEY=$A_KEY
SLACK_WEBHOOK_URL=$S_WEBHOOK
MAX_COMMENTS_PER_DAY=$MAX_DAILY
MIN_COMMENT_INTERVAL_MINUTES=$MIN_INTERVAL
QUALITY_THRESHOLD=$QUALITY
CYCLE_INTERVAL_HOURS=$CYCLE_HRS
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
fi

chmod 600 "$ENV_FILE"
info "Configuration saved to $ENV_FILE"

# ─── Step 3: Initialize database ──────────────────────────────

.venv/bin/python -c "from src.db import init_db; init_db()" 2>/dev/null
info "Database initialized"

# ─── Step 4: Health check ─────────────────────────────────────

echo ""
.venv/bin/python -m src.health 2>/dev/null && HC_OK=true || HC_OK=false

# ─── Step 5: Create convenience commands ───────────────────────

# Create a wrapper script
cat > "$INSTALL_DIR/reddit-agent" <<'WRAPPER'
#!/usr/bin/env bash
cd "$(dirname "$0")"
exec .venv/bin/python -m src.main "$@"
WRAPPER
chmod +x "$INSTALL_DIR/reddit-agent"

# Symlink to PATH if possible
if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$INSTALL_DIR/reddit-agent" "$HOME/.local/bin/reddit-agent"
    info "Command 'reddit-agent' available in PATH"
elif [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "$INSTALL_DIR/reddit-agent" "/usr/local/bin/reddit-agent"
    info "Command 'reddit-agent' available in PATH"
fi

# ─── Step 6: OpenClaw integration (if available) ──────────────

OPENCLAW_DIR="$HOME/.openclaw"
if [ -d "$OPENCLAW_DIR" ]; then
    echo ""
    echo -e "${BOLD}OpenClaw Integration${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Create OpenClaw skill
    SKILL_DIR="$OPENCLAW_DIR/skills/reddit-agent"
    mkdir -p "$SKILL_DIR"
    cat > "$SKILL_DIR/SKILL.md" <<'SKILL_EOF'
---
name: reddit-agent
description: "Autonomous Reddit engagement agent. Scans subreddits, evaluates threads, generates human-like comments, posts via browser, and learns from feedback. Commands: reddit-agent (run cycle), reddit-agent --feedback (check past comments), reddit-agent --digest (daily report). Use when: the user wants to post on Reddit, check Reddit engagement, run the Reddit bot, get a Reddit digest, or manage Reddit automation."
allowed-tools: Bash(reddit-agent *), Bash(cat ~/.reddit-agent/data/learnings.md), Bash(cat ~/.reddit-agent/data/subreddit_reports/*), Read, Edit
---

# Reddit Agent

Autonomous Reddit engagement agent powered by browser-use + Claude API.

## Commands

```bash
# Run one engagement cycle (scan, evaluate, generate, post)
reddit-agent

# Run feedback loop only (check past comments, detect shadowbans)
reddit-agent --feedback

# Send daily digest to Slack
reddit-agent --digest
```

## Configuration

All config is in `~/.reddit-agent/.env`. Edit to change:
- `MAX_COMMENTS_PER_DAY` — daily posting limit (default: 5)
- `MIN_COMMENT_INTERVAL_MINUTES` — cooldown between posts (default: 20)
- `QUALITY_THRESHOLD` — minimum quality score 1-10 (default: 7)

## Subreddit Config

Edit `~/.reddit-agent/data/subreddits.yaml` to add/remove target subreddits.

Each subreddit has: keywords, max daily comments, tone guidance, and community notes.

## Monitoring

- **Learnings:** `~/.reddit-agent/data/learnings.md` — what the agent has learned
- **Intel reports:** `~/.reddit-agent/data/subreddit_reports/` — per-subreddit analysis
- **Database:** `~/.reddit-agent/data/reddit.db` — full history
- **Screenshots:** `~/.reddit-agent/data/screenshots/` — error screenshots

## How It Works

1. Scans target subreddits for relevant threads
2. Evaluates each thread's engagement opportunity (Claude API)
3. Generates a human-like comment (Claude API)
4. Scores comment quality before posting (naturalness, relevance, safety, subtlety)
5. Posts via headless browser with anti-detection stealth
6. Verifies comment visibility (shadowban detection)
7. Tracks karma and learns from feedback over time
SKILL_EOF

    info "OpenClaw skill installed at $SKILL_DIR"

    # Offer to set up cron
    if [ "${1:-}" != "--non-interactive" ]; then
        echo ""
        ask "Set up OpenClaw cron job to run every ${CYCLE_HRS:-2} hours? [Y/n]:"
        read -r SETUP_CRON
        SETUP_CRON="${SETUP_CRON:-Y}"
    else
        SETUP_CRON="Y"
    fi

    if [ "$SETUP_CRON" = "Y" ] || [ "$SETUP_CRON" = "y" ]; then
        CRON_FILE="$OPENCLAW_DIR/cron/jobs.json"
        # Use Python to update the cron JSON
        .venv/bin/python -c "
import json
cron_path = '$CRON_FILE'
try:
    with open(cron_path) as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {'version': 1, 'jobs': []}

# Remove existing reddit-agent job if any
data['jobs'] = [j for j in data.get('jobs', []) if j.get('name') != 'reddit-agent']

# Add new job
data['jobs'].append({
    'name': 'reddit-agent',
    'schedule': '0 */${CYCLE_HRS:-2} * * *',
    'command': '$INSTALL_DIR/reddit-agent',
    'description': 'Run Reddit engagement cycle',
    'enabled': True
})

with open(cron_path, 'w') as f:
    json.dump(data, f, indent=2)
print('Cron job registered')
" 2>/dev/null
        info "OpenClaw cron job set: every ${CYCLE_HRS:-2} hours"
    fi
fi

# ─── Done ─────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "Quick start:"
echo "  reddit-agent              # Run one cycle"
echo "  reddit-agent --feedback   # Check past comments"
echo "  reddit-agent --digest     # Send daily report"
echo ""
echo "Config:     $INSTALL_DIR/.env"
echo "Subreddits: $INSTALL_DIR/data/subreddits.yaml"
echo "Learnings:  $INSTALL_DIR/data/learnings.md"
echo ""
if [ -d "$OPENCLAW_DIR" ]; then
    echo "OpenClaw: Skill installed. Your agent can now run 'reddit-agent' directly."
    echo ""
fi
