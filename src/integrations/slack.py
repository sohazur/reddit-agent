"""Slack notifications for the Reddit agent."""

import json

import requests

from src.config import Config
from src.log import get_logger

log = get_logger("slack")


def send_notification(config: Config, message: str) -> bool:
    """Send a message to the configured Slack webhook."""
    if not config.slack_webhook_url:
        log.warning("No Slack webhook configured, skipping notification")
        return False

    try:
        response = requests.post(
            config.slack_webhook_url,
            json={"text": message},
            timeout=10,
        )
        if response.status_code == 200:
            return True

        log.error(f"Slack notification failed: {response.status_code}")
        return False
    except requests.RequestException as e:
        log.error(f"Slack notification error: {e}")
        return False


def send_cycle_summary(config: Config, results: dict) -> None:
    """Send a cycle completion summary to Slack."""
    msg = (
        f"*Reddit Agent — Cycle Complete*\n"
        f"Threads scanned: {results.get('threads_scanned', 0)}\n"
        f"Threads evaluated: {results.get('threads_evaluated', 0)}\n"
        f"Comments posted: {results.get('comments_posted', 0)}\n"
        f"Comments skipped (quality): {results.get('comments_skipped', 0)}\n"
        f"Errors: {results.get('errors', 0)}"
    )
    send_notification(config, msg)


def send_daily_digest(config: Config, summary: dict) -> None:
    """Send the daily digest to Slack."""
    best = summary.get("best_comment")
    best_text = ""
    if best:
        best_text = (
            f"\nBest: r/{best['subreddit']} got +{best.get('karma', 0)} karma"
        )

    survival_rate = 0
    if summary["comments_posted"] > 0:
        survival_rate = (
            summary["comments_surviving"] / summary["comments_posted"] * 100
        )

    msg = (
        f"*Reddit Agent — Daily Report ({summary['date']})*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Comments posted: {summary['comments_posted']}\n"
        f"Comments surviving: {summary['comments_surviving']}/{summary['comments_posted']} "
        f"({survival_rate:.0f}%)\n"
        f"Comments removed: {summary['comments_removed']}"
        f"{best_text}\n"
        f"Karma gained today: {summary['karma_gained']:+d}"
    )
    send_notification(config, msg)


def send_alert(config: Config, level: str, message: str) -> None:
    """Send an alert with severity level."""
    emoji = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(level, "")
    msg = f"{emoji} *Reddit Agent — {level}*\n{message}"
    send_notification(config, msg)
