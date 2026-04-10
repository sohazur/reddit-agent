#!/usr/bin/env bash
set -euo pipefail

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Reddit Agent — Installer
#
#  Install:  pip install reddit-agent@git+https://github.com/sohazur/reddit-agent
#  Or:       curl -fsSL https://raw.githubusercontent.com/sohazur/reddit-agent/main/install.sh | bash
#  Or:       ./install.sh
#
#  Updates:  reddit-agent-update  (pulls latest from GitHub)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INSTALL_DIR="${REDDIT_AGENT_DIR:-$HOME/.reddit-agent}"
REPO_URL="https://github.com/sohazur/reddit-agent.git"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[X]${NC} $*"; }

echo ""
echo -e "${BOLD}Reddit Agent${NC} — Autonomous Reddit engagement for OpenClaw"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── Prerequisites ─────────────────────────────────

# Python
if ! command -v python3 &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        echo "Installing Python..."
        apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip >/dev/null 2>&1
    elif command -v brew &>/dev/null; then
        brew install python@3.12 >/dev/null 2>&1
    else
        err "Python 3.12+ required. Install it first."
        exit 1
    fi
fi
info "Python $(python3 --version 2>&1 | awk '{print $2}')"

# uv (fast package manager)
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh >/dev/null 2>&1
    export PATH="$HOME/.local/bin:$PATH"
fi
if command -v uv &>/dev/null; then
    PKG_MGR="uv"
    info "uv $(uv --version 2>&1 | head -1)"
else
    PKG_MGR="pip"
    info "pip (fallback)"
fi

# git
if ! command -v git &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        apt-get install -y -qq git >/dev/null 2>&1
    fi
fi

# ─── Install / Update ─────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet 2>/dev/null || true
    info "Updated to latest version"
else
    echo "Installing..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null
    info "Cloned repository"
fi

cd "$INSTALL_DIR"

# Python venv + deps
if [ "$PKG_MGR" = "uv" ]; then
    uv venv .venv --quiet 2>/dev/null
    uv pip install -e ".[dev]" --quiet 2>/dev/null
else
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]" --quiet 2>/dev/null
fi
info "Dependencies installed"

# Playwright + Chromium
.venv/bin/playwright install chromium 2>/dev/null || {
    .venv/bin/playwright install-deps chromium 2>/dev/null || true
    .venv/bin/playwright install chromium 2>/dev/null
}
info "Chromium installed"

# ─── Configuration ─────────────────────────────────

ENV_FILE="$INSTALL_DIR/.env"

if [ "${1:-}" = "--non-interactive" ]; then
    # Non-interactive: REDDIT_USERNAME + REDDIT_PASSWORD from env
    if [ -z "${REDDIT_USERNAME:-}" ] || [ -z "${REDDIT_PASSWORD:-}" ]; then
        err "Need REDDIT_USERNAME and REDDIT_PASSWORD env vars"
        exit 1
    fi
    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=${REDDIT_USERNAME}
REDDIT_PASSWORD=${REDDIT_PASSWORD}
MAX_COMMENTS_PER_DAY=${MAX_COMMENTS_PER_DAY:-5}
MIN_COMMENT_INTERVAL_MINUTES=${MIN_COMMENT_INTERVAL_MINUTES:-20}
QUALITY_THRESHOLD=${QUALITY_THRESHOLD:-7}
CYCLE_INTERVAL_HOURS=${CYCLE_INTERVAL_HOURS:-2}
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
elif [ ! -f "$ENV_FILE" ] || grep -q "placeholder" "$ENV_FILE" 2>/dev/null; then
    echo ""
    echo -e "${BOLD}Setup${NC} — I just need your Reddit credentials."
    echo ""
    printf "Reddit username: "
    read -r R_USER
    printf "Reddit password: "
    read -rs R_PASS
    echo ""
    printf "Max comments/day [5]: "
    read -r MAX_DAILY
    MAX_DAILY="${MAX_DAILY:-5}"

    cat > "$ENV_FILE" <<EOF
REDDIT_USERNAME=$R_USER
REDDIT_PASSWORD=$R_PASS
MAX_COMMENTS_PER_DAY=$MAX_DAILY
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
CYCLE_INTERVAL_HOURS=2
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
    info "Credentials saved"
else
    info "Using existing config"
fi

chmod 600 "$ENV_FILE"

# ─── Initialize ───────────────────────────────────

.venv/bin/python -c "from src.db import init_db; init_db()" 2>/dev/null
info "Database ready"

# ─── Commands ─────────────────────────────────────

# Main command
cat > "$INSTALL_DIR/reddit-agent" <<'CMD'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
# Source shell env for API keys
[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true
exec .venv/bin/python -m src.main "$@"
CMD
chmod +x "$INSTALL_DIR/reddit-agent"

# Update command
cat > "$INSTALL_DIR/reddit-agent-update" <<CMD
#!/usr/bin/env bash
echo "Updating Reddit Agent..."
cd "$INSTALL_DIR"
git pull 2>&1
if [ "$PKG_MGR" = "uv" ]; then
    uv pip install -e ".[dev]" --quiet 2>/dev/null
else
    .venv/bin/pip install -e ".[dev]" --quiet 2>/dev/null
fi
echo "Updated to \$(git log --oneline -1)"
CMD
chmod +x "$INSTALL_DIR/reddit-agent-update"

# Symlink to PATH
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/reddit-agent" "$HOME/.local/bin/reddit-agent"
ln -sf "$INSTALL_DIR/reddit-agent-update" "$HOME/.local/bin/reddit-agent-update"
info "Commands: reddit-agent, reddit-agent-update"

# ─── OpenClaw Integration ─────────────────────────

OPENCLAW_SKILLS=""
for dir in "$HOME/.openclaw/agents/skills" "$HOME/.openclaw/skills"; do
    [ -d "$dir" ] && OPENCLAW_SKILLS="$dir" && break
done

if [ -n "$OPENCLAW_SKILLS" ]; then
    SKILL_DIR="$OPENCLAW_SKILLS/reddit-agent"
    mkdir -p "$SKILL_DIR"
    cp "$INSTALL_DIR/openclaw/SKILL.md" "$SKILL_DIR/SKILL.md"
    info "OpenClaw skill installed"

    # Register cron
    for cron_file in "$HOME/.openclaw/cron/jobs.json"; do
        [ -f "$cron_file" ] || continue
        .venv/bin/python -c "
import json, os
path = '$cron_file'
interval = os.environ.get('CYCLE_INTERVAL_HOURS', '2')
with open(path) as f:
    data = json.load(f)
data['jobs'] = [j for j in data.get('jobs', []) if j.get('name') != 'reddit-agent']
data['jobs'].append({
    'id': 'reddit-agent-cycle',
    'agentId': 'main',
    'name': 'reddit-agent',
    'enabled': True,
    'schedule': {'kind': 'cron', 'expr': '0 */' + interval + ' * * *', 'tz': 'UTC'},
    'sessionTarget': 'isolated',
    'wakeMode': 'next-heartbeat',
    'payload': {
        'kind': 'agentTurn',
        'text': 'Run: reddit-agent. Report the results to me.'
    },
    'state': {}
})
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null
        info "OpenClaw cron: every ${CYCLE_INTERVAL_HOURS:-2}h"
        break
    done

    # Add to HEARTBEAT.md
    for heartbeat in "$HOME/.openclaw/workspace/HEARTBEAT.md" "$HOME/clawd/HEARTBEAT.md"; do
        [ -f "$heartbeat" ] || continue
        if ! grep -q "reddit-agent" "$heartbeat" 2>/dev/null; then
            cat >> "$heartbeat" <<'HB'

## Reddit Agent
- [ ] If reddit-agent cron hasn't run in >3h, run: reddit-agent
- [ ] If user asks about Reddit: reddit-agent --digest
HB
            info "Added to HEARTBEAT.md"
        fi
        break
    done
fi

# ─── Done ─────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}Reddit Agent installed!${NC}"
echo ""
echo "  reddit-agent              Run one cycle"
echo "  reddit-agent --feedback   Check past comments"
echo "  reddit-agent --digest     Performance report"
echo "  reddit-agent-update       Pull latest updates"
echo ""
echo "  Config:     $INSTALL_DIR/.env"
echo "  Subreddits: $INSTALL_DIR/data/subreddits.yaml"
echo ""
if [ -n "$OPENCLAW_SKILLS" ]; then
    echo "  OpenClaw:   Skill + cron installed"
    echo "              Say 'run the Reddit agent' in chat"
fi
echo ""
echo "  Next: Set up cookies for VM access (see README.md)"
echo ""
