"""Per-account persona: one consistent human identity across months.

The stealth layer makes a single comment look human; the persona makes the WHOLE
account look like one coherent person over time — same voice tics, interests,
and rough backstory in every comment, instead of a different vibe each session.

Persona lives in data/persona.yaml so it persists and can be hand-edited. If it
doesn't exist, the agent runs without one (no behavior change) — it's generated
on demand via `ensure_persona`.
"""

from pathlib import Path

import yaml

from src.config import DATA_DIR
from src.log import get_logger

log = get_logger("persona")

PERSONA_PATH = DATA_DIR / "persona.yaml"

# Active-hours intentionally omitted: scheduling lives in the driving agent, and
# nothing in the generation path consumes an hours window (see CEO review #7).
_PERSONA_FIELDS = ("voice", "interests", "backstory", "quirks")


def load_persona() -> dict:
    """Load the persona dict, or {} if none exists / is unreadable."""
    if not PERSONA_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(PERSONA_PATH.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log.warning(f"Could not read persona.yaml: {e}")
        return {}


def persona_prompt(persona: dict | None = None) -> str:
    """Render the persona as an instruction block for generation.

    Returns "" when there's no persona, so callers can append unconditionally.
    """
    persona = persona if persona is not None else load_persona()
    if not persona:
        return ""

    lines = ["You are ONE consistent person. Stay in character every time:"]
    if persona.get("backstory"):
        lines.append(f"- Backstory: {persona['backstory']}")
    if persona.get("interests"):
        interests = persona["interests"]
        if isinstance(interests, list):
            interests = ", ".join(str(i) for i in interests)
        lines.append(f"- Interests: {interests}")
    if persona.get("voice"):
        lines.append(f"- Voice: {persona['voice']}")
    if persona.get("quirks"):
        quirks = persona["quirks"]
        if isinstance(quirks, list):
            quirks = ", ".join(str(q) for q in quirks)
        lines.append(f"- Quirks: {quirks}")

    return "\n".join(lines) if len(lines) > 1 else ""


def save_persona(persona: dict) -> None:
    """Persist a persona dict to data/persona.yaml."""
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: persona[k] for k in _PERSONA_FIELDS if k in persona}
    PERSONA_PATH.write_text(yaml.safe_dump(clean, sort_keys=False))
    log.info(f"Saved persona to {PERSONA_PATH}")


def ensure_persona(config) -> dict:
    """Return the existing persona, or generate + persist one from the objective.

    Generation is best-effort: on any LLM error we return {} and the agent runs
    without a persona (no behavior change).
    """
    existing = load_persona()
    if existing:
        return existing

    from src.llm import call_llm

    domain = getattr(config, "domain", "") or "general topics"
    prompt = (
        "Invent a believable, low-key Reddit persona for someone who is "
        f"knowledgeable about {domain}. Keep it ordinary and human, not a "
        "marketer. Respond with ONLY a JSON object with keys: "
        '"voice" (1 sentence on writing style), '
        '"interests" (3-5 short items), '
        '"backstory" (1-2 sentences, mundane), '
        '"quirks" (2-3 short writing tics).'
    )
    try:
        import json

        text = call_llm(prompt, max_tokens=400)
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        persona = json.loads(text)
        if isinstance(persona, dict) and persona:
            save_persona(persona)
            return load_persona()
    except Exception as e:
        log.warning(f"Could not generate persona, running without one: {e}")
    return {}
