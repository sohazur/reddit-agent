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
#   REDDIT_AGENT_BIN   path to the reddit-agent executable (default: reddit-agent on PATH)
#   REDDIT_AGENT_DIR   install dir, used to locate .env (default: $HOME/.reddit-agent)
set -euo pipefail

BIN="${REDDIT_AGENT_BIN:-reddit-agent}"
AGENT_DIR="${REDDIT_AGENT_DIR:-$HOME/.reddit-agent}"

if ! command -v "$BIN" >/dev/null 2>&1 && [ ! -x "$BIN" ]; then
  echo "heartbeat: reddit-agent binary not found ($BIN)" >&2
  exit 1
fi

# Load .env if present so cron/systemd (which have a bare environment) see config.
if [ -f "$AGENT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$AGENT_DIR/.env"
  set +a
fi

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

status_json="$("$BIN" --status 2>/dev/null || true)"
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
    echo "$(ts) heartbeat: PAUSED — circuit breaker tripped. Not running. Investigate, then: $BIN --resume"
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
  "$BIN" --digest >/dev/null 2>&1 || true
  echo "$today" > "$DIGEST_STAMP"
  echo "$(ts) heartbeat: sent daily digest"
fi

if is_true "should_run"; then
  echo "$(ts) heartbeat: should_run=true — running a cycle"
  "$BIN"
  echo "$(ts) heartbeat: cycle complete"
else
  echo "$(ts) heartbeat: should_run=false — nothing to do this tick"
fi
