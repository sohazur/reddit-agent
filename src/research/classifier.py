"""Classify a Reddit post as a (potential) opportunity for our services.

Pure LLM-call + JSON-parse. Splitting parse_classification() out makes the
fragile bit (model output → typed result) unit-testable without a network call.
"""

import json
from dataclasses import dataclass, field

from src.config import Config, ServiceCatalog, load_prompt
from src.llm import call_llm
from src.log import get_logger
from src.research.services import format_services_block, valid_service_ids

log = get_logger("research.classifier")


@dataclass
class Opportunity:
    is_opportunity: bool
    priority: int
    confidence: float
    matched_services: list[str] = field(default_factory=list)
    problem_summary: str = ""
    suggested_angle: str = ""


def _clamp_int(v, lo: int, hi: int, default: int = 0) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _clamp_float(v, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def parse_classification(text: str, known_service_ids: set[str]) -> Opportunity:
    """Parse the classifier's JSON response into an Opportunity.

    Defensive: tolerates code fences, unknown service ids, and missing fields,
    and fails closed (is_opportunity=False) on anything unparseable.
    """
    if not text:
        return Opportunity(False, 0, 0.0)

    raw = text.strip()
    if "```" in raw:
        # Take the content of the last fenced block.
        raw = raw.split("```json")[-1].split("```")[0].strip()
        if not raw:
            raw = text.strip().split("```")[-2] if text.count("```") >= 2 else ""

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        log.warning("Could not parse classification JSON")
        return Opportunity(False, 0, 0.0)

    if not isinstance(data, dict):
        return Opportunity(False, 0, 0.0)

    matched = data.get("matched_services") or []
    if not isinstance(matched, list):
        matched = []
    # Drop hallucinated service ids; we only act on configured services.
    if known_service_ids:
        matched = [m for m in matched if m in known_service_ids]

    is_opp = bool(data.get("is_opportunity", False))
    priority = _clamp_int(data.get("priority", 0), 0, 10)
    # An "opportunity" with no matched service and no priority isn't actionable.
    if is_opp and not matched and priority == 0:
        is_opp = False

    return Opportunity(
        is_opportunity=is_opp,
        priority=priority,
        confidence=_clamp_float(data.get("confidence", 0.0), 0.0, 1.0),
        matched_services=matched,
        problem_summary=str(data.get("problem_summary", "")).strip(),
        suggested_angle=str(data.get("suggested_angle", "")).strip(),
    )


async def classify_opportunity(
    config: Config,
    catalog: ServiceCatalog,
    subreddit: str,
    thread_title: str,
    thread_body: str,
    thread_comments: str,
) -> Opportunity:
    """Ask the LLM whether this thread is a real opportunity for our services."""
    prompt = load_prompt(
        "classify_opportunity",
        company_name=catalog.company_name or "our company",
        company_url=catalog.company_url or "",
        company_one_liner=catalog.company_one_liner or "",
        services_block=format_services_block(catalog),
        audiences=", ".join(catalog.audiences) or "anyone who needs these services",
        objective=config.objective or "find people we can genuinely help",
        subreddit=subreddit,
        thread_title=thread_title,
        thread_body=(thread_body or "")[:2500],
        thread_comments=(thread_comments or "")[:2500],
    )

    try:
        text = call_llm(prompt, max_tokens=400)
    except Exception as e:
        log.error(f"Classifier LLM error: {e}")
        return Opportunity(False, 0, 0.0)

    return parse_classification(text, valid_service_ids(catalog))
