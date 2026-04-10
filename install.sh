#!/usr/bin/env bash
set -euo pipefail

# Reddit Agent — One-command installer
#
# Designed to be run by an OpenClaw agent OR a human.
# The agent can run: ./install.sh --non-interactive
# and pass only REDDIT_USERNAME + REDDIT_PASSWORD.
#
# API keys: Uses the host environment (OpenClaw's shell env injects them).
# Messaging: The agent itself handles notifications (WhatsApp/Telegram/etc).
# No Slack needed. No separate Anthropic key needed.

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
    # Try to install Python
    if command -v apt-get &>/dev/null; then
        info "Installing Python 3..."
        apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip >/dev/null 2>&1
    elif command -v brew &>/dev/null; then
        info "Installing Python 3 via Homebrew..."
        brew install python@3.12 >/dev/null 2>&1
    else
        err "Python 3 not found and can't auto-install. Install Python 3.12+ first."
        exit 1
    fi
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VERSION"

# Check/install uv (fast Python package manager)
if ! command -v uv &>/dev/null; then
    info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh >/dev/null 2>&1
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        # Fall back to pip
        PKG_MGR="pip"
        info "Using pip (uv not available)"
    else
        PKG_MGR="uv"
        info "uv installed"
    fi
else
    PKG_MGR="uv"
    info "uv found"
fi

# Check/install git
if ! command -v git &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        apt-get install -y -qq git >/dev/null 2>&1
    fi
fi

# ─── Step 1: Install the project ───────────────────────────────

if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/pyproject.toml" ]; then
    info "Existing installation found, updating..."
    cd "$INSTALL_DIR"
    if [ -d .git ]; then
        git pull --quiet 2>/dev/null || true
    fi
else
    # Clone or copy
    if [ -d "$(dirname "$0")/src" ] && [ -f "$(dirname "$0")/pyproject.toml" ]; then
        cp -r "$(cd "$(dirname "$0")" && pwd)" "$INSTALL_DIR"
        info "Copied from local directory"
    elif command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/sohazur/reddit-agent.git "$INSTALL_DIR" 2>/dev/null || {
            err "Clone failed. Copy the project manually to $INSTALL_DIR"
            exit 1
        }
        info "Cloned from GitHub"
    else
        err "git not found and not running from source. Install git or copy project to $INSTALL_DIR"
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
.venv/bin/playwright install chromium 2>/dev/null || {
    # On Linux, may need system deps
    .venv/bin/playwright install-deps chromium 2>/dev/null || true
    .venv/bin/playwright install chromium 2>/dev/null
}
info "Chromium browser installed"

# ─── Step 2: Configuration ─────────────────────────────────────

echo ""
ENV_FILE="$INSTALL_DIR/.env"

if [ "${1:-}" = "--non-interactive" ]; then
    # Non-interactive: use env vars or defaults
    # Only REDDIT_USERNAME and REDDIT_PASSWORD are truly required
    if [ -z "${REDDIT_USERNAME:-}" ] || [ -z "${REDDIT_PASSWORD:-}" ]; then
        err "Non-interactive mode requires REDDIT_USERNAME and REDDIT_PASSWORD env vars"
        exit 1
    fi

    # Try to find Anthropic key from environment (OpenClaw usually has it)
    API_KEY="${ANTHROPIC_API_KEY:-${OPENAI_API_KEY:-}}"
    if [ -z "$API_KEY" ]; then
        # Check if OpenClaw has shell env enabled — keys may be available at runtime
        warn "No API key found in env. The OpenClaw agent will use its own LLM access."
        API_KEY="agent-provided"
    fi

    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=${REDDIT_USERNAME}
REDDIT_PASSWORD=${REDDIT_PASSWORD}
ANTHROPIC_API_KEY=${API_KEY}
MAX_COMMENTS_PER_DAY=${MAX_COMMENTS_PER_DAY:-5}
MIN_COMMENT_INTERVAL_MINUTES=${MIN_COMMENT_INTERVAL_MINUTES:-20}
QUALITY_THRESHOLD=${QUALITY_THRESHOLD:-7}
CYCLE_INTERVAL_HOURS=${CYCLE_INTERVAL_HOURS:-2}
LOG_LEVEL=${LOG_LEVEL:-INFO}
SCREENSHOT_ON_ERROR=true
EOF

else
    # Interactive mode — only ask what's absolutely necessary
    echo -e "${BOLD}I just need your Reddit account credentials.${NC}"
    echo "(Everything else is auto-configured.)"
    echo ""

    ask "Reddit username:"
    read -r R_USER
    ask "Reddit password:"
    read -rs R_PASS
    echo ""

    # Try to find API key from environment
    API_KEY="${ANTHROPIC_API_KEY:-${OPENAI_API_KEY:-}}"
    if [ -z "$API_KEY" ]; then
        echo ""
        ask "Anthropic API key (or press Enter if OpenClaw provides it):"
        read -rs A_KEY
        echo ""
        API_KEY="${A_KEY:-agent-provided}"
    else
        info "Found API key in environment"
    fi

    # Cadence defaults (just confirm or customize)
    echo ""
    ask "Max comments per day [5]:"
    read -r MAX_DAILY
    MAX_DAILY="${MAX_DAILY:-5}"

    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=$R_USER
REDDIT_PASSWORD=$R_PASS
ANTHROPIC_API_KEY=$API_KEY
MAX_COMMENTS_PER_DAY=$MAX_DAILY
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
CYCLE_INTERVAL_HOURS=2
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
fi

chmod 600 "$ENV_FILE"
info "Configuration saved"

# ─── Step 3: Initialize database ──────────────────────────────

.venv/bin/python -c "from src.db import init_db; init_db()" 2>/dev/null
info "Database initialized"

# ─── Step 4: Create wrapper command ───────────────────────────

cat > "$INSTALL_DIR/reddit-agent" <<'WRAPPER'
#!/usr/bin/env bash
cd "$(dirname "$0")"
exec .venv/bin/python -m src.main "$@"
WRAPPER
chmod +x "$INSTALL_DIR/reddit-agent"

# Add to PATH
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/reddit-agent" "$HOME/.local/bin/reddit-agent"
export PATH="$HOME/.local/bin:$PATH"
info "Command 'reddit-agent' installed"

# ─── Step 5: OpenClaw integration ─────────────────────────────

OPENCLAW_DIR="$HOME/.openclaw"
CLAWD_DIR="$HOME/clawd"

if [ -d "$OPENCLAW_DIR" ]; then
    echo ""
    info "OpenClaw detected — installing skill"

    # Install skill
    SKILL_DIR="$OPENCLAW_DIR/skills/reddit-agent"
    mkdir -p "$SKILL_DIR"
    if [ -f "$INSTALL_DIR/openclaw/SKILL.md" ]; then
        cp "$INSTALL_DIR/openclaw/SKILL.md" "$SKILL_DIR/SKILL.md"
    fi

    # Register cron job
    CRON_FILE="$OPENCLAW_DIR/cron/jobs.json"
    if [ -f "$CRON_FILE" ]; then
        .venv/bin/python -c "
import json, os
cron_path = '$CRON_FILE'
interval = os.environ.get('CYCLE_INTERVAL_HOURS', '2')
try:
    with open(cron_path) as f:
        data = json.load(f)
except:
    data = {'version': 1, 'jobs': []}
data['jobs'] = [j for j in data.get('jobs', []) if j.get('name') != 'reddit-agent']
data['jobs'].append({
    'name': 'reddit-agent',
    'schedule': f'0 */{interval} * * *',
    'command': '$INSTALL_DIR/reddit-agent',
    'description': 'Run Reddit engagement cycle',
    'enabled': True
})
with open(cron_path, 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null
        info "Cron job registered (every ${CYCLE_INTERVAL_HOURS:-2}h)"
    fi

    # Add to HEARTBEAT.md if it exists and doesn't already mention reddit
    if [ -f "$CLAWD_DIR/HEARTBEAT.md" ]; then
        if ! grep -q "reddit-agent" "$CLAWD_DIR/HEARTBEAT.md" 2>/dev/null; then
            cat >> "$CLAWD_DIR/HEARTBEAT.md" <<'HEARTBEAT'

## Reddit Agent
- [ ] If reddit-agent cron hasn't run in >3h, run: reddit-agent
- [ ] If user asks about Reddit performance: reddit-agent --digest
HEARTBEAT
            info "Added Reddit tasks to HEARTBEAT.md"
        fi
    fi
fi

# ─── Step 6: Health check ─────────────────────────────────────

echo ""
.venv/bin/python -m src.health 2>/dev/null || true

# ─── Done ─────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}Reddit Agent installed!${NC}"
echo ""
echo "  reddit-agent              # Run one cycle"
echo "  reddit-agent --feedback   # Check past comments"
echo "  reddit-agent --digest     # Daily report"
echo ""
echo "  Config:     $INSTALL_DIR/.env"
echo "  Subreddits: $INSTALL_DIR/data/subreddits.yaml"
echo ""
if [ -d "$OPENCLAW_DIR" ]; then
    echo "  OpenClaw: Skill + cron installed. Say 'run reddit agent' in chat."
fi
echo ""
