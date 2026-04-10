"""CSV tracker integration (ai-marketing compatible).

Logs activity to both the local DB and optionally to the
ai-marketing social media tracker CSV.
"""

import csv
from datetime import datetime
from pathlib import Path

from src.config import Config
from src.log import get_logger

log = get_logger("tracker")


def log_activity(
    config: Config,
    platform: str,
    action_type: str,
    url: str,
    content_summary: str,
    status: str = "posted",
    engagement_notes: str = "pending",
) -> None:
    """Log an activity to the ai-marketing tracker CSV if configured.

    Follows the schema from ai-marketing/.claude/rules/social-media-tracker.md:
    date,platform,action_type,url,content_summary,status,engagement_notes
    """
    if not config.ai_marketing_tracker_path:
        return

    tracker_path = config.ai_marketing_tracker_path
    if not tracker_path.exists():
        log.warning(f"Tracker CSV not found: {tracker_path}")
        return

    try:
        with open(tracker_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.utcnow().strftime("%Y-%m-%d"),
                platform,
                action_type,
                url,
                content_summary[:200],
                status,
                engagement_notes,
            ])
        log.info(f"Logged {action_type} to tracker CSV")
    except Exception as e:
        log.error(f"Failed to write to tracker CSV: {e}")
