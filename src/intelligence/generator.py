"""Generate Reddit comments using LLM."""

from src.config import Config, SubredditConfig, load_prompt, LEARNINGS_PATH
from src.llm import call_llm
from src.log import get_logger

log = get_logger("generator")


def _load_learnings(subreddit_name: str) -> str:
    """Load relevant learnings for the subreddit."""
    if not LEARNINGS_PATH.exists():
        return "No prior learnings available yet."

    content = LEARNINGS_PATH.read_text()
    lines = content.split("\n")
    relevant = []
    capturing = False

    for line in lines:
        if f"r/{subreddit_name}" in line:
            capturing = True
            relevant.append(line)
        elif capturing and line.startswith("## "):
            capturing = False
        elif capturing:
            relevant.append(line)

    if relevant:
        return "\n".join(relevant[-30:])

    return content[-2000:] if len(content) > 2000 else content


def _load_exemplars(subreddit_name: str, min_exemplars: int = 2) -> str:
    """Load proven top comments as few-shot exemplars for this subreddit.

    Only comments that survived a feedback check qualify (see db.get_top_comments).
    Min-sample guard: if fewer than `min_exemplars` qualify, inject nothing
    rather than anchoring on one weak example. New accounts get no block.
    """
    from src.db import get_top_comments

    try:
        top = get_top_comments(subreddit_name, limit=3, min_karma=5)
    except Exception as e:
        log.warning(f"Could not load exemplars: {e}")
        return ""

    if len(top) < min_exemplars:
        return ""

    lines = [
        f"{i}. (+{c['karma']}) {c['comment_text']}"
        for i, c in enumerate(top, 1)
    ]
    return (
        "Your best-performing comments in this community (write in THIS spirit):\n"
        + "\n".join(lines)
    )


def _load_subreddit_intel(subreddit_name: str) -> str:
    """Load subreddit intelligence report if available."""
    from src.db import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT report_json FROM subreddit_intel WHERE subreddit = ?",
            (subreddit_name,),
        ).fetchone()
        if row:
            return row[0]
    return ""


_TIER_GUIDANCE = {
    1: "TIER 1 — pure value. Just be genuinely helpful or interesting about the "
       "topic. Do NOT mention any product, company, or yourself. Build credibility.",
    2: "TIER 2 — topic content with light relevance. Share real experience in the "
       "domain. You may allude to having worked on this kind of thing, but do NOT "
       "name or pitch a product. Stay an expert, not a seller.",
    3: "TIER 3 — direct mention is allowed but must feel natural and rare. Only "
       "name the product if it genuinely answers the question; one mention max, "
       "no sales language.",
}


def _build_objective(config: Config, tier: int) -> str:
    """Combine objective, domain, and tier framing into one instruction."""
    objective = config.objective or "Be helpful and build authority in the community."
    domain = getattr(config, "domain", "")
    parts = [objective]
    if domain:
        parts.append(f"Your area of expertise: {domain}.")
    parts.append(_TIER_GUIDANCE.get(tier, _TIER_GUIDANCE[1]))
    return "\n".join(parts)


async def generate_comment(
    config: Config,
    subreddit: SubredditConfig,
    thread_title: str,
    thread_body: str,
    thread_comments: str,
    karma_mode: bool = False,
    tier: int = 1,
) -> str:
    """Generate a human-like comment for a Reddit thread.

    If karma_mode=True, generates a purely genuine comment with no brand agenda.
    `tier` (1/2/3) controls how much brand relevance the content carries.
    """
    learnings = _load_learnings(subreddit.name)
    intel = _load_subreddit_intel(subreddit.name)
    exemplars = _load_exemplars(subreddit.name)

    tone = subreddit.tone
    if intel:
        tone = f"{subreddit.tone}\n\nSubreddit intelligence: {intel}"
    if exemplars:
        learnings = f"{learnings}\n\n{exemplars}"

    # Karma mode is always pure value (tier 1) regardless of requested tier.
    effective_tier = 1 if karma_mode else tier
    objective = _build_objective(config, effective_tier)
    template = "generate_comment_karma" if karma_mode else "generate_comment"
    prompt = load_prompt(
        template,
        subreddit_name=subreddit.name,
        subreddit_tone=tone,
        subreddit_notes=subreddit.notes,
        thread_title=thread_title,
        thread_body=thread_body[:2000],
        thread_comments=thread_comments[:3000],
        learnings_context=learnings,
        objective=objective,
    )

    try:
        comment = call_llm(prompt, max_tokens=500)

        if not comment:
            log.error("Generated empty comment")
            return ""

        if len(comment) > 2000:
            comment = comment[:2000]
            log.info("Trimmed comment to 2000 chars")

        if comment.startswith('"') and comment.endswith('"'):
            comment = comment[1:-1]

        log.info(f"Generated comment ({len(comment)} chars): {comment[:80]}...")
        return comment

    except Exception as e:
        log.error(f"LLM error during generation: {e}")
        return ""
