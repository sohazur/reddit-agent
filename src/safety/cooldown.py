"""Per-subreddit cooldowns after a removal.

When a post/comment is removed (by a mod or Reddit's spam filter — see the
ThinkTax3983 Dubai post "removed by Reddit's filters"), the right human response
is: stop posting there for a while, understand why, and don't repeat the mistake.

This stores a cooldown per subreddit with the captured reason and an expiry, in
data/cooldowns.json. The cycle checks is_on_cooldown(sub) before posting, and the
reason is fed into learnings so generation avoids the same framing next time.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.config import DATA_DIR
from src.log import get_logger

log = get_logger("cooldown")

COOLDOWN_PATH = DATA_DIR / "cooldowns.json"
DEFAULT_COOLDOWN_DAYS = 3


@dataclass
class Cooldown:
    subreddit: str
    reason: str
    until: str  # ISO timestamp


def _load() -> dict:
    if not COOLDOWN_PATH.exists():
        return {}
    try:
        return json.loads(COOLDOWN_PATH.read_text()) or {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    COOLDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_PATH.write_text(json.dumps(data, indent=2))


def start_cooldown(subreddit: str, reason: str, days: int = DEFAULT_COOLDOWN_DAYS) -> None:
    """Pause posting in a subreddit for `days`, recording why."""
    data = _load()
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    data[subreddit.lower()] = {"reason": reason, "until": until}
    _save(data)
    log.warning(f"Cooldown started for r/{subreddit} ({days}d): {reason}")


def is_on_cooldown(subreddit: str) -> bool:
    """True if the subreddit is currently cooling down (expired ones are cleared)."""
    data = _load()
    entry = data.get(subreddit.lower())
    if not entry:
        return False
    try:
        until = datetime.fromisoformat(entry["until"])
    except (KeyError, ValueError):
        return False
    if datetime.now(timezone.utc) >= until:
        # Expired — clean it up.
        data.pop(subreddit.lower(), None)
        _save(data)
        return False
    return True


def active_cooldowns() -> list[Cooldown]:
    """All currently-active cooldowns (for status reporting)."""
    out = []
    for sub, entry in _load().items():
        if is_on_cooldown(sub):
            out.append(Cooldown(sub, entry.get("reason", ""), entry.get("until", "")))
    return out
