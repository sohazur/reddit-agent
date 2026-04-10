"""Pre-post quality gate using LLM."""

import json
from dataclasses import dataclass

from src.config import Config, load_prompt
from src.llm import call_llm
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
    """Score a comment before posting. Only post if passed=True."""
    prompt = load_prompt(
        "quality_check",
        comment_text=comment_text,
        subreddit_name=subreddit_name,
        thread_title=thread_title,
    )

    try:
        text = call_llm(prompt, max_tokens=300)

        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()

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
        return QualityScore(5, 5, 5, 5, 5.0, False, "Failed to parse quality response")
    except Exception as e:
        log.error(f"LLM error during quality check: {e}")
        return QualityScore(0, 0, 0, 0, 0.0, False, f"API error: {e}")
