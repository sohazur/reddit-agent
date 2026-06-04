"""Learning layer for Research mode.

Summarizes what the agent has observed — which posts get traction, where the
opportunities cluster — into data/research_insights.md. This is the "becomes a
comprehensive agent that learns what people ask and what goes viral" piece.
"""

from datetime import datetime

from src.config import RESEARCH_INSIGHTS_PATH
from src.log import get_logger
from src.research import store

log = get_logger("research.insights")


def _cluster_by_subreddit(opportunities: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for o in opportunities:
        sub = o.get("subreddit") or "?"
        counts[sub] = counts.get(sub, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)


def render_insights(
    opportunities: list[dict],
    viral: list[dict],
    opp_counts: dict,
) -> str:
    """Pure renderer for the insights markdown."""
    lines = [
        "# Research Insights",
        f"_Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Opportunity pipeline",
        f"- Total tracked: {opp_counts.get('total', 0)}",
        f"- New (not yet pushed): {opp_counts.get('new', 0)}",
        f"- Pushed to platform: {opp_counts.get('pushed', 0)}",
        "",
        "## Where opportunities cluster",
    ]
    clusters = _cluster_by_subreddit(opportunities)
    if clusters:
        for sub, n in clusters[:15]:
            lines.append(f"- r/{sub}: {n}")
    else:
        lines.append("- (none yet)")

    lines.extend(["", "## What gets traction (top observed posts)"])
    if viral:
        for v in viral[:15]:
            lines.append(
                f"- {v.get('score', 0)} upvotes / {v.get('comment_count', 0)} comments "
                f"— r/{v.get('subreddit') or '?'}: {v.get('title')}"
            )
    else:
        lines.append("- (no high-traction posts observed yet)")

    lines.extend([
        "",
        "## Read this as",
        "Lean discovery + outreach toward the subreddits at the top of the cluster "
        "list, and study the high-traction posts for the angles/titles that earn "
        "attention in this niche.",
        "",
    ])
    return "\n".join(lines)


def update_research_insights() -> None:
    """Read the store and (re)write data/research_insights.md."""
    opportunities = store.get_opportunities(limit=500)
    viral = store.get_top_viral(limit=20, min_score=30)
    opp_counts = store.count_opportunities()

    RESEARCH_INSIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_INSIGHTS_PATH.write_text(
        render_insights(opportunities, viral, opp_counts)
    )
    log.info("Updated research insights")
