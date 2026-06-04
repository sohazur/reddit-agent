"""Render the opportunity list to Markdown + JSON, and build the push payload.

render_markdown / build_payload are pure so they can be tested directly; the
write_outputs() wrapper reads the store and writes the files on disk.
"""

from datetime import datetime

from src.config import (
    OPPORTUNITIES_JSON,
    OPPORTUNITIES_MD,
    ServiceCatalog,
)
from src.log import get_logger
from src.research import store
from src.research.services import pitches_for

log = get_logger("research.report")


def _service_names(catalog: ServiceCatalog, ids: list[str]) -> list[str]:
    by_id = {s.id: s.name for s in catalog.services}
    return [by_id.get(i, i) for i in ids]


def render_markdown(
    opportunities: list[dict],
    catalog: ServiceCatalog,
    viral: list[dict] | None = None,
) -> str:
    """Human-readable, ranked lead list."""
    company = catalog.company_name or "Your company"
    lines = [
        f"# {company} — Reddit Opportunities",
        f"_Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(opportunities)} open opportunities_",
        "",
        "Ranked list of Reddit posts where one of our services is a genuine fit. "
        "Nothing here was posted — this is research for outreach.",
        "",
    ]

    if not opportunities:
        lines.append("_No open opportunities yet. The agent is still scanning._")
    for i, o in enumerate(opportunities, 1):
        svc_names = _service_names(catalog, o.get("matched_services", []))
        lines.extend([
            f"## {i}. [{o.get('title') or '(untitled)'}]({o.get('url')})",
            f"- **Priority:** {o.get('priority', 0)}/10"
            f"  ·  **Subreddit:** r/{o.get('subreddit') or '?'}"
            f"  ·  **Author:** u/{o.get('author') or '?'}",
            f"- **Problem:** {o.get('problem_summary') or '—'}",
            f"- **Services that fit:** {', '.join(svc_names) or '—'}",
            f"- **How we'd help:** {o.get('suggested_angle') or '—'}",
        ])
        pitches = pitches_for(catalog, o.get("matched_services", []))
        for p in pitches:
            lines.append(f"    - {p}")
        lines.append("")

    if viral:
        lines.extend(["", "## What's getting traction (learning signal)", ""])
        for v in viral:
            lines.append(
                f"- [{v.get('title')}]({v.get('url')}) — "
                f"{v.get('score', 0)} upvotes, {v.get('comment_count', 0)} comments "
                f"(r/{v.get('subreddit') or '?'})"
            )
        lines.append("")

    return "\n".join(lines)


def build_payload(opportunities: list[dict], catalog: ServiceCatalog) -> dict:
    """Machine-readable payload for the JSON file and the platform push."""
    return {
        "company": catalog.company_name,
        "generated_at": datetime.utcnow().isoformat(),
        "count": len(opportunities),
        "opportunities": [
            {
                "id": o.get("id"),
                "url": o.get("url"),
                "title": o.get("title"),
                "subreddit": o.get("subreddit"),
                "author": o.get("author"),
                "priority": o.get("priority", 0),
                "confidence": o.get("confidence", 0),
                "problem_summary": o.get("problem_summary"),
                "matched_services": o.get("matched_services", []),
                "suggested_angle": o.get("suggested_angle"),
                "found_at": o.get("found_at"),
                "status": o.get("status"),
            }
            for o in opportunities
        ],
    }


def write_outputs(catalog: ServiceCatalog, limit: int = 200) -> dict:
    """Write opportunities.md + opportunities.json from the store. Returns payload."""
    import json

    opportunities = store.get_opportunities(limit=limit)
    viral = store.get_top_viral(limit=10)

    OPPORTUNITIES_MD.parent.mkdir(parents=True, exist_ok=True)
    OPPORTUNITIES_MD.write_text(render_markdown(opportunities, catalog, viral))

    payload = build_payload(opportunities, catalog)
    OPPORTUNITIES_JSON.write_text(json.dumps(payload, indent=2))

    log.info(f"Wrote {len(opportunities)} opportunities to {OPPORTUNITIES_MD.name}")
    return payload
