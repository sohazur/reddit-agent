"""Self-audit + auto-heal watchdog for unattended 24/7 operation.

Runs at the start of every cycle (and on demand via `reddit-agent --audit`).
It looks for the failure modes that quietly break a long-running agent and
fixes the safe ones itself — no human needed. Problems it cannot safely fix on
its own (missing credentials, an expired cookie jar, a tripped circuit breaker)
are escalated as alerts so the human knows exactly what to do.

Design: each checker is a small pure function over paths/values so it can be
unit-tested with tmp dirs; healing and alerting are layered on top.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    Config,
    DATA_DIR,
    DB_PATH,
    PROMPTS_DIR,
    SCREENSHOTS_DIR,
    SERVICES_PATH,
    MAX_SCREENSHOTS,
    prune_screenshots,
)
from src.log import get_logger

log = get_logger("watchdog")

COOKIES_PATH = DATA_DIR / "cookies.json"


@dataclass
class Issue:
    code: str
    severity: str  # info | warning | critical
    detail: str
    auto_fixable: bool


# ─── Checkers (pure) ───────────────────────────────────────────────────────


def check_db_initialized(db_path: Path) -> Issue | None:
    if not db_path.exists():
        return Issue("db_missing", "warning", "Database not initialized", True)
    return None


def check_screenshot_overflow(screenshots_dir: Path, cap: int) -> Issue | None:
    try:
        pngs = list(screenshots_dir.glob("*.png"))
    except OSError:
        return None
    if len(pngs) > cap:
        return Issue(
            "screenshot_overflow", "warning",
            f"{len(pngs)} error screenshots (cap {cap}) — likely repeated failures",
            True,
        )
    return None


def check_cookies(cookies_path: Path, max_age_days: int = 25) -> Issue | None:
    """Missing cookies → critical (login will fail). Old cookies → warning."""
    if not cookies_path.exists():
        return Issue(
            "cookies_missing", "critical",
            "data/cookies.json missing — Reddit login will fail. Re-export cookies.",
            False,
        )
    age_days = (
        datetime.now(timezone.utc).timestamp() - cookies_path.stat().st_mtime
    ) / 86400
    if age_days > max_age_days:
        return Issue(
            "cookies_stale", "warning",
            f"Cookies are {age_days:.0f} days old — may expire soon; consider re-export.",
            False,
        )
    return None


def check_services_present(services_path: Path, research_mode: str) -> Issue | None:
    if research_mode != "off" and not services_path.exists():
        return Issue(
            "services_missing", "warning",
            "RESEARCH_MODE is on but data/services.yaml is missing — research idles.",
            False,
        )
    return None


def check_disk_space(data_dir: Path, min_free_mb: int = 100) -> Issue | None:
    try:
        free_mb = shutil.disk_usage(data_dir).free / (1024 * 1024)
    except OSError:
        return None
    if free_mb < min_free_mb:
        return Issue(
            "low_disk", "critical",
            f"Only {free_mb:.0f} MB free on the data volume.",
            True,  # we can free space by pruning screenshots
        )
    return None


def check_breaker_paused() -> Issue | None:
    from src.safety.breaker import get_state
    state = get_state()
    if state.paused:
        return Issue(
            "paused", "critical",
            f"Circuit breaker tripped: {state.reason} (since {state.since}). "
            f"Posting halted until `reddit-agent --resume`.",
            False,
        )
    return None


# ─── Orchestration ─────────────────────────────────────────────────────────


def audit(config: Config) -> list[Issue]:
    """Collect all current issues (no side effects)."""
    issues = []
    for chk in (
        check_db_initialized(DB_PATH),
        check_screenshot_overflow(SCREENSHOTS_DIR, MAX_SCREENSHOTS),
        check_cookies(COOKIES_PATH),
        check_services_present(SERVICES_PATH, config.research_mode),
        check_disk_space(DATA_DIR),
        check_breaker_paused(),
    ):
        if chk:
            issues.append(chk)
    return issues


def _heal(issue: Issue) -> bool:
    """Attempt to auto-fix one issue. Returns True if fixed."""
    try:
        if issue.code == "db_missing":
            from src.db import init_db
            init_db()
            return True
        if issue.code in ("screenshot_overflow", "low_disk"):
            # Keep only a few on overflow / free space aggressively on low disk.
            prune_screenshots(keep=5 if issue.code == "low_disk" else MAX_SCREENSHOTS)
            return True
    except Exception as e:
        log.error(f"Auto-heal failed for {issue.code}: {e}")
    return False


def run_watchdog(config: Config, heal: bool = True, alert: bool = True) -> dict:
    """Audit, auto-heal what's safe, escalate the rest. Returns a report dict."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    issues = audit(config)
    healed: list[str] = []
    escalated: list[Issue] = []

    for issue in issues:
        if heal and issue.auto_fixable and _heal(issue):
            healed.append(issue.code)
            log.info(f"Watchdog auto-healed: {issue.code} ({issue.detail})")
        else:
            escalated.append(issue)
            level = log.error if issue.severity == "critical" else log.warning
            level(f"Watchdog issue [{issue.severity}] {issue.code}: {issue.detail}")

    if alert and escalated:
        _alert_escalated(config, escalated)

    return {
        "healed": healed,
        "escalated": [
            {"code": i.code, "severity": i.severity, "detail": i.detail}
            for i in escalated
        ],
        "ok": not escalated,
    }


def _alert_escalated(config: Config, escalated: list[Issue]) -> None:
    """Send one consolidated Slack alert for issues we couldn't auto-fix."""
    try:
        from src.integrations.slack import send_alert
        worst = "CRITICAL" if any(i.severity == "critical" for i in escalated) else "WARNING"
        body = "\n".join(f"- [{i.severity}] {i.code}: {i.detail}" for i in escalated)
        send_alert(config, worst, f"Watchdog found issues it can't auto-fix:\n{body}")
    except Exception as e:
        log.error(f"Failed to send watchdog alert: {e}")


def print_audit(config: Config) -> None:
    """Human-readable audit for `reddit-agent --audit` (no healing)."""
    import json
    issues = audit(config)
    report = {
        "checked_at": datetime.utcnow().isoformat(),
        "issues": [
            {
                "code": i.code, "severity": i.severity,
                "detail": i.detail, "auto_fixable": i.auto_fixable,
            }
            for i in issues
        ],
        "ok": not issues,
    }
    print(json.dumps(report, indent=2))
