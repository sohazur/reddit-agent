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


async def generate_comment(
    config: Config,
    subreddit: SubredditConfig,
    thread_title: str,
    thread_body: str,
    thread_comments: str,
) -> str:
    """Generate a human-like comment for a Reddit thread."""
    learnings = _load_learnings(subreddit.name)
    intel = _load_subreddit_intel(subreddit.name)

    tone = subreddit.tone
    if intel:
        tone = f"{subreddit.tone}\n\nSubreddit intelligence: {intel}"

    prompt = load_prompt(
        "generate_comment",
        subreddit_name=subreddit.name,
        subreddit_tone=tone,
        subreddit_notes=subreddit.notes,
        thread_title=thread_title,
        thread_body=thread_body[:2000],
        thread_comments=thread_comments[:3000],
        learnings_context=learnings,
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
