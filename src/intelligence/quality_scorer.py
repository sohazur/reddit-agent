"""Pre-post quality gate using Claude API."""

import json
from dataclasses import dataclass

import anthropic

from src.config import Config, load_prompt
from src.log import get_logger

log = get_logger("quality_scorer")


@dataclass
class QualityScore:
    naturalness: float
    relevance: float
    brand_safety: float
    subtlety: float
    average: float
    passed: bool
    issues: str


async def score_comment(
    config: Config,
    comment_text: str,
    subreddit_name: str,
    thread_title: str,
) -> QualityScore:
    """Score a comment before posting.

    Returns a QualityScore. The comment should only be posted if passed=True.
    """
    prompt = load_prompt(
        "quality_check",
        comment_text=comment_text,
        subreddit_name=subreddit_name,
        thread_title=thread_title,
    )

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
            if not text:
                text = response.content[0].text.split("```")[-2].strip()

        data = json.loads(text)

        score = QualityScore(
            naturalness=data.get("naturalness", 0),
            relevance=data.get("relevance", 0),
            brand_safety=data.get("brand_safety", 0),
            subtlety=data.get("subtlety", 0),
            average=data.get("average", 0),
            passed=data.get("pass", False),
            issues=data.get("issues", ""),
        )

        if score.passed:
            log.info(f"Quality check PASSED (avg: {score.average})")
        else:
            log.warning(f"Quality check FAILED (avg: {score.average}): {score.issues}")

        return score

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse quality score: {e}")
        # Fail open — let the comment through but flag it
        return QualityScore(5, 5, 5, 5, 5.0, False, "Failed to parse quality response")
    except anthropic.APIError as e:
        log.error(f"Claude API error during quality check: {e}")
        # Fail closed on API errors — don't post without quality check
        return QualityScore(0, 0, 0, 0, 0.0, False, f"API error: {e}")
