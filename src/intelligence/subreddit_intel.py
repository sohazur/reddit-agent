"""Generate subreddit intelligence reports."""

import json
from datetime import datetime

import anthropic

from src.config import Config, SubredditConfig, load_prompt, SUBREDDIT_REPORTS_DIR
from src.db import get_connection
from src.log import get_logger

log = get_logger("subreddit_intel")


async def generate_intel_report(
    config: Config,
    browser_session,
    subreddit: SubredditConfig,
    force: bool = False,
) -> dict | None:
    """Generate an intelligence report for a subreddit.

    Checks if a recent report exists (< 7 days). If so, returns it
    unless force=True.
    """
    # Check for existing recent report
    if not force:
        existing = _get_existing_report(subreddit.name)
        if existing:
            log.info(f"Using existing intel report for r/{subreddit.name}")
            return existing

    log.info(f"Generating intel report for r/{subreddit.name}")

    # Gather data from the subreddit
    from src.browser.actions import extract_subreddit_data

    try:
        sub_data = await extract_subreddit_data(browser_session, subreddit.name)
    except Exception as e:
        log.error(f"Failed to gather data for r/{subreddit.name}: {e}")
        return None

    top_posts = "\n".join(
        f"- [{p['title']}] (score: {p.get('score', '?')}, comments: {p.get('comment_count', '?')})"
        for p in sub_data.get("posts", [])[:30]
    )

    sample_comments = "\n".join(
        f"- {c.get('author', 'anon')}: {c.get('body', '')[:200]}"
        for c in sub_data.get("sample_comments", [])[:20]
    )

    sidebar_rules = sub_data.get("sidebar", "Not available")

    prompt = load_prompt(
        "subreddit_intel",
        subreddit_name=subreddit.name,
        top_posts=top_posts,
        sample_comments=sample_comments,
        sidebar_rules=sidebar_rules[:2000],
    )

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
            if not text:
                text = response.content[0].text.split("```")[-2].strip()

        report = json.loads(text)

        # Save to DB
        _save_report(subreddit.name, report, len(sub_data.get("posts", [])))

        # Save human-readable report to file
        _save_report_file(subreddit.name, report)

        log.info(f"Intel report generated for r/{subreddit.name}")
        return report

    except (json.JSONDecodeError, anthropic.APIError) as e:
        log.error(f"Failed to generate intel report: {e}")
        return None


def _get_existing_report(subreddit_name: str) -> dict | None:
    """Get an existing report if it's less than 7 days old."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT report_json, generated_at FROM subreddit_intel
               WHERE subreddit = ?
               AND julianday('now') - julianday(generated_at) < 7""",
            (subreddit_name,),
        ).fetchone()

        if row:
            return json.loads(row[0])
    return None


def _save_report(subreddit_name: str, report: dict, post_count: int) -> None:
    """Save report to SQLite."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO subreddit_intel
               (subreddit, report_json, generated_at, post_count_analyzed)
               VALUES (?, ?, ?, ?)""",
            (subreddit_name, json.dumps(report),
             datetime.utcnow().isoformat(), post_count),
        )


def _save_report_file(subreddit_name: str, report: dict) -> None:
    """Save a human-readable report to the subreddit_reports directory."""
    SUBREDDIT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SUBREDDIT_REPORTS_DIR / f"{subreddit_name}.md"

    lines = [
        f"# r/{subreddit_name} Intelligence Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**Tone:** {report.get('tone', 'Unknown')}",
        f"**Avg comment length:** {report.get('avg_comment_length', 'Unknown')}",
        f"**Self-promotion tolerance:** {report.get('self_promotion_tolerance', 'Unknown')}",
        f"**Mod activity:** {report.get('mod_activity', 'Unknown')}",
        "",
        "## Hot Topics",
    ]
    for topic in report.get("hot_topics", []):
        lines.append(f"- {topic}")

    lines.extend([
        "",
        f"**What gets upvoted:** {report.get('what_gets_upvoted', '')}",
        f"**What gets downvoted:** {report.get('what_gets_downvoted', '')}",
        "",
        "## Best Engagement Style",
        report.get("best_engagement_style", ""),
        "",
        "## Avoid",
    ])
    for item in report.get("avoid", []):
        lines.append(f"- {item}")

    path.write_text("\n".join(lines))
