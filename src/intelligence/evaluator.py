"""Evaluate thread relevance using LLM."""

import json
from dataclasses import dataclass

from src.config import Config, SubredditConfig, load_prompt
from src.llm import call_llm
from src.log import get_logger

log = get_logger("evaluator")


@dataclass
class ThreadScore:
    relevance: int
    opportunity: int
    risk: int
    timing: int
    total: int
    reasoning: str


async def evaluate_thread(
    config: Config,
    subreddit: SubredditConfig,
    thread_title: str,
    thread_body: str,
    thread_score: int,
    thread_comment_count: int,
    thread_comments: str,
) -> ThreadScore:
    """Score a thread's relevance and engagement opportunity."""
    prompt = load_prompt(
        "evaluate_thread",
        subreddit_name=subreddit.name,
        subreddit_tone=subreddit.tone,
        subreddit_notes=subreddit.notes,
        thread_title=thread_title,
        thread_body=thread_body[:2000],
        thread_score=str(thread_score),
        thread_comment_count=str(thread_comment_count),
        thread_comments=thread_comments[:3000],
    )

    try:
        text = call_llm(prompt, max_tokens=300)

        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()

        data = json.loads(text)

        score = ThreadScore(
            relevance=data.get("relevance", 0),
            opportunity=data.get("opportunity", 0),
            risk=data.get("risk", 0),
            timing=data.get("timing", 0),
            total=data.get("total", 0),
            reasoning=data.get("reasoning", ""),
        )

        log.info(f"Thread scored {score.total}/10: {score.reasoning}")
        return score

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse evaluation response: {e}")
        return ThreadScore(0, 0, 0, 0, 0, "Failed to parse response")
    except Exception as e:
        log.error(f"LLM error during evaluation: {e}")
        return ThreadScore(0, 0, 0, 0, 0, f"API error: {e}")
