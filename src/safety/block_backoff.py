"""Adaptive backoff after a Reddit network-security block.

When a research pass is cut short by Reddit's IP-level "blocked by network
security" 403, hammering it again only deepens the block — Reddit escalates
repeat offenders from a minutes-long velocity block to a multi-hour one. So we
record a cool-down here and have the driver (heartbeat / status) skip research
until it expires. Consecutive blocks back off further (5m → 20m → 60m, capped).

State lives in data/block_backoff.json, written atomically.
"""

import json
import os
from datetime import datetime, timezone

from src.config import DATA_DIR
from src.log import get_logger

log = get_logger("block_backoff")

BACKOFF_PATH = DATA_DIR / "block_backoff.json"

# Escalating wait per consecutive block (seconds). Index clamped to last entry.
_STEPS_S = [300, 1200, 3600]  # 5 min, 20 min, 60 min


def _load() -> dict:
    if not BACKOFF_PATH.exists():
        return {}
    try:
        return json.loads(BACKOFF_PATH.read_text()) or {}
    except (json.JSONDecodeError, ValueError) as e:
        log.warning(f"block_backoff.json unreadable ({e}); treating as none")
        return {}


def _save(data: dict) -> None:
    BACKOFF_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(BACKOFF_PATH) + ".tmp"
    with open(tmp, "w") as f:
        f.write(json.dumps(data, indent=2))
    os.replace(tmp, str(BACKOFF_PATH))


def record_block(now: datetime | None = None) -> int:
    """Record a network block; return the chosen backoff in seconds.

    Consecutive blocks escalate the wait. Pass `now` for testability.
    """
    now = now or datetime.now(timezone.utc)
    data = _load()
    streak = int(data.get("consecutive", 0)) + 1
    wait_s = _STEPS_S[min(streak - 1, len(_STEPS_S) - 1)]
    until = now.timestamp() + wait_s
    _save({"consecutive": streak, "until_ts": until,
           "recorded_at": now.isoformat()})
    log.warning(
        f"Network block #{streak} — backing off research {wait_s // 60}min"
    )
    return wait_s


def clear() -> None:
    """Clear the backoff after a successful (unblocked) pass."""
    if BACKOFF_PATH.exists():
        try:
            BACKOFF_PATH.unlink()
        except OSError:
            _save({})


def seconds_remaining(now: datetime | None = None) -> int:
    """Seconds until research may run again (0 if clear/expired)."""
    now = now or datetime.now(timezone.utc)
    data = _load()
    until = data.get("until_ts")
    if not until:
        return 0
    remaining = int(until - now.timestamp())
    return remaining if remaining > 0 else 0


def is_backing_off(now: datetime | None = None) -> bool:
    """True if research should currently hold off due to a recent block."""
    return seconds_remaining(now) > 0
