#!/usr/bin/env bash
#
# materialize_secrets.sh — turn env-var secrets into the files the agent needs.
#
# Secret stores (Claude Code on the web, CI, most PaaS) hold ENV VARS, not files.
# But Reddit login needs data/cookies.json on disk. This script bridges that: it
# decodes a base64 cookie blob from an env var into data/cookies.json, so you can
# keep everything in your environment's secret config and nothing in git.
#
# Set ONE of these in your environment:
#   REDDIT_COOKIES_B64   base64 of your cookies.json   (recommended)
#   REDDIT_COOKIES       raw cookies.json text
#
# Reddit creds are read straight from the environment by the agent, so you only
# need: REDDIT_USERNAME, REDDIT_PASSWORD, and (optionally) ANTHROPIC_API_KEY.
#
# Run this once at container/session start (e.g. from a SessionStart hook or
# your systemd ExecStartPre) before `reddit-agent`.
set -euo pipefail

ROOT="${REDDIT_AGENT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
COOKIES="$ROOT/data/cookies.json"
mkdir -p "$ROOT/data"

if [ -n "${REDDIT_COOKIES_B64:-}" ]; then
  printf '%s' "$REDDIT_COOKIES_B64" | base64 -d > "$COOKIES"
  chmod 600 "$COOKIES"
  echo "materialize_secrets: wrote $COOKIES from REDDIT_COOKIES_B64"
elif [ -n "${REDDIT_COOKIES:-}" ]; then
  printf '%s' "$REDDIT_COOKIES" > "$COOKIES"
  chmod 600 "$COOKIES"
  echo "materialize_secrets: wrote $COOKIES from REDDIT_COOKIES"
elif [ -f "$COOKIES" ]; then
  echo "materialize_secrets: $COOKIES already present — leaving as is"
else
  echo "materialize_secrets: WARNING — no cookies provided. Reddit login will fail." >&2
fi

# Sanity-check the cookie JSON is parseable (don't print contents).
if [ -f "$COOKIES" ] && command -v python3 >/dev/null 2>&1; then
  python3 -c "import json,sys; json.load(open('$COOKIES')); print('materialize_secrets: cookies.json is valid JSON')" \
    || { echo 'materialize_secrets: ERROR — cookies.json is not valid JSON' >&2; exit 1; }
fi
