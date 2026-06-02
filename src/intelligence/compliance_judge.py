"""LLM fuzzy-rule judge for compliance.

Separate from the deterministic gate so that module stays pure and LLM-free.
INVARIANT: this judge may only ADD blocks. It is called only AFTER the
deterministic gate has ALLOWED a comment. A timeout, parse error, or refusal
counts as a BLOCK (fail closed).
"""

import json
from dataclasses import dataclass

from src.config import Config, load_prompt
from src.llm import call_llm
from src.log import get_logger

log = get_logger("compliance_judge")


@dataclass
class JudgeResult:
    compliant: bool
    reason: str


async def judge_fuzzy_compliance(
    config: Config,
    comment_text: str,
    subreddit_name: str,
    thread_title: str,
    rules: str,
) -> JudgeResult:
    """Judge subjective rule compliance. Fails closed on any error."""
    prompt = load_prompt(
        "compliance_judge",
        subreddit_name=subreddit_name,
        rules=rules or "No explicit rules available.",
        thread_title=thread_title,
        comment_text=comment_text,
    )

    try:
        text = call_llm(prompt, max_tokens=200)
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        data = json.loads(text)
        compliant = bool(data.get("compliant", False))
        reason = str(data.get("reason", ""))
        if not compliant:
            log.warning(f"Fuzzy judge BLOCKED: {reason}")
        return JudgeResult(compliant=compliant, reason=reason)
    except json.JSONDecodeError as e:
        log.error(f"Fuzzy judge unparseable response, failing closed: {e}")
        return JudgeResult(compliant=False, reason="judge response unparseable")
    except Exception as e:
        log.error(f"Fuzzy judge error, failing closed: {e}")
        return JudgeResult(compliant=False, reason=f"judge error: {e}")
