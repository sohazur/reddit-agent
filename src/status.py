"""Status report for the driving agent.

The agent (Claude/OpenClaw) is the scheduler. This module gives it a clean,
machine-readable snapshot so it can decide when to run, when to back off, and
when to alert the human. Scheduling logic stays in the agent; the tool just
reports state. See AGENT_LOOP.md for the loop the agent runs.
"""

import json
from datetime import datetime, timezone

from src.config import DATA_DIR, Config
from src.db import get_today_comment_count
from src.log import get_logger

log = get_logger("status")

LOCKFILE = DATA_DIR / "agent.lock"


def _last_run_iso() -> str | None:
    """When the last cycle started, from the lockfile mtime (written each run)."""
    if not LOCKFILE.exists():
        return None
    ts = LOCKFILE.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def build_status(config: Config) -> dict:
    """Build the status snapshot the driving agent consumes."""
    from src.safety.breaker import get_state

    last_run = _last_run_iso()
    hours_since = None
    if last_run:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(last_run)
        hours_since = round(delta.total_seconds() / 3600, 2)

    paused = get_state()
    comments_today = get_today_comment_count()
    limit = config.max_comments_per_day
    quota_left = max(0, limit - comments_today)

    interval = config.cycle_interval_hours
    # The agent should run when: not paused, quota remains, and enough time has
    # passed since the last run (or it has never run).
    should_run = (
        not paused.paused
        and quota_left > 0
        and (hours_since is None or hours_since >= interval)
    )

    alerts = []
    if paused.paused:
        alerts.append(f"PAUSED: {paused.reason} (since {paused.since}) — "
                      f"run `reddit-agent --resume` after investigating")
    if quota_left == 0:
        alerts.append("daily comment quota reached")

    return {
        "last_run": last_run,
        "hours_since": hours_since,
        "cycle_interval_hours": interval,
        "should_run": should_run,
        "paused": paused.paused,
        "paused_reason": paused.reason if paused.paused else None,
        "dry_run": config.dry_run,
        "today": {
            "comments": comments_today,
            "comment_limit": limit,
            "quota_left": quota_left,
        },
        "alerts": alerts,
    }


def print_status(config: Config) -> None:
    """Print the status snapshot as JSON for the driving agent to parse."""
    print(json.dumps(build_status(config), indent=2))
