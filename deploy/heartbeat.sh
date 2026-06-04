#!/usr/bin/env bash
#
# heartbeat.sh — one tick of the agent loop (see AGENT_LOOP.md).
#
# Runs `reddit-agent --status`, and only runs a cycle when the tool says it's
# safe to (should_run). Honors the circuit breaker (never runs while paused).
# Designed to be invoked periodically by cron, systemd timer, or launchd — NOT
# a long-running daemon.
#
# Exit codes: 0 = tick handled (ran or correctly skipped), 1 = setup error.
#
# Env:
#   REDDIT_AGENT_DIR   install dir (default: $HOME/.reddit-agent). Used to locate
#                      .env, stamps, and to cd into before running.
#   REDDIT_AGENT_CMD   full command to invoke the agent (default: the installed
#                      `reddit-agent` binary). For a venv/source checkout set it
#                      to e.g. ".venv/bin/python -m src.main".
set -euo pipefail

AGENT_DIR="${REDDIT_AGENT_DIR:-$HOME/.reddit-agent}"
CMD="${REDDIT_AGENT_CMD:-reddit-agent}"

# Run from the install dir so relative paths (.venv, data/, src/) resolve.
cd "$AGENT_DIR" 2>/dev/null || { echo "heartbeat: dir not found ($AGENT_DIR)" >&2; exit 1; }

# `agent` runs the command (with any args) as one invocation.
agent() { eval "$CMD \"\$@\""; }

# Load .env if present so cron/systemd (which have a bare environment) see config.
if [ -f "$AGENT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$AGENT_DIR/.env"
  set +a
fi

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

status_json="$(agent --status 2>/dev/null || true)"
if [ -z "$status_json" ]; then
  echo "$(ts) heartbeat: could not read status" >&2
  exit 1
fi

# Minimal JSON probes (no jq dependency).
is_true()  { printf '%s' "$status_json" | grep -q "\"$1\": *true"; }

# Research mode is read-only, so it stays productive even while posting is paused.
research_on=false
if printf '%s' "$status_json" | grep -Eq '"research_mode": *"(after_quota|only)"'; then
  research_on=true
fi

if is_true "paused"; then
  if [ "$research_on" = false ]; then
    echo "$(ts) heartbeat: PAUSED — circuit breaker tripped. Not running. Investigate, then: $CMD --resume"
    # Surface the alert text for whoever reads the logs.
    printf '%s\n' "$status_json" | grep -A20 '"alerts"' || true
    exit 0
  fi
  echo "$(ts) heartbeat: PAUSED — posting halted, but research continues (read-only)"
fi

# Once-a-day digest: send on the first successful tick after UTC midnight.
DIGEST_STAMP="$AGENT_DIR/.last-digest-date"
today="$(date -u +%Y-%m-%d)"
if [ ! -f "$DIGEST_STAMP" ] || [ "$(cat "$DIGEST_STAMP" 2>/dev/null)" != "$today" ]; then
  agent --digest >/dev/null 2>&1 || true
  echo "$today" > "$DIGEST_STAMP"
  echo "$(ts) heartbeat: sent daily digest"
fi

if is_true "should_run"; then
  echo "$(ts) heartbeat: should_run=true — running a cycle"
  agent
  echo "$(ts) heartbeat: cycle complete"
else
  echo "$(ts) heartbeat: should_run=false — nothing to do this tick"
fi
