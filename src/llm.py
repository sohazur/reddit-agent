"""LLM abstraction layer.

Auto-detects which API is available (Anthropic, OpenAI, or environment)
and provides a unified interface for the intelligence layer.
No manual API key configuration needed — uses whatever the host has.
"""

import json
import os
import subprocess
from src.log import get_logger

log = get_logger("llm")

_client = None
_provider = None


def _detect_provider() -> tuple[str, str]:
    """Detect which LLM provider is available.

    Checks in order:
    1. ANTHROPIC_API_KEY in env or .bashrc
    2. OPENAI_API_KEY in env or .bashrc
    3. Claude CLI (claude command)

    Returns (provider, api_key) tuple.
    """
    # Check environment
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key and anthropic_key != "agent-provided":
        return "anthropic", anthropic_key

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return "openai", openai_key

    # Check .bashrc / .profile for keys
    for rc_file in [os.path.expanduser("~/.bashrc"), os.path.expanduser("~/.profile")]:
        if os.path.exists(rc_file):
            try:
                with open(rc_file) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("export ANTHROPIC_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key and key != "agent-provided":
                                return "anthropic", key
                        if line.startswith("export OPENAI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key:
                                return "openai", key
            except Exception:
                continue

    # Check OpenClaw config for auth profiles
    openclaw_config = os.path.expanduser("~/.openclaw/openclaw.json")
    if os.path.exists(openclaw_config):
        try:
            with open(openclaw_config) as f:
                data = json.load(f)
            auth = data.get("auth", {})
            profiles = auth.get("profiles", {})
            # Check for stored keys in profiles
            for name, prof in profiles.items():
                if prof.get("api_key"):
                    provider = prof.get("provider", "")
                    if provider in ("anthropic", "openai"):
                        return provider, prof["api_key"]
        except Exception:
            pass

    raise RuntimeError(
        "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in the environment."
    )


def get_provider() -> str:
    """Get the detected LLM provider name."""
    global _provider
    if _provider is None:
        _provider, _ = _detect_provider()
        log.info(f"LLM provider: {_provider}")
    return _provider


def call_llm(
    prompt: str,
    max_tokens: int = 500,
    model: str | None = None,
    images: list[dict] | None = None,
) -> str:
    """Call the LLM with a prompt and return the response text.

    Auto-detects the provider and uses the appropriate SDK.
    Supports optional image inputs for vision tasks (CAPTCHA solving).
    """
    provider, api_key = _detect_provider()

    if provider == "anthropic":
        return _call_anthropic(prompt, api_key, max_tokens, model, images)
    elif provider == "openai":
        return _call_openai(prompt, api_key, max_tokens, model, images)
    else:
        raise RuntimeError(f"Unknown provider: {provider}")


def _call_anthropic(
    prompt: str, api_key: str, max_tokens: int, model: str | None, images: list | None
) -> str:
    """Call Anthropic Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    model = model or "claude-sonnet-4-20250514"

    messages_content = []
    if images:
        for img in images:
            messages_content.append(img)
    messages_content.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": messages_content}],
    )
    return response.content[0].text.strip()


def _call_openai(
    prompt: str, api_key: str, max_tokens: int, model: str | None, images: list | None
) -> str:
    """Call OpenAI API."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = model or "gpt-4o"

    messages_content = []
    if images:
        for img in images:
            # Convert Anthropic image format to OpenAI format
            if img.get("type") == "image" and img.get("source", {}).get("type") == "base64":
                media_type = img["source"].get("media_type", "image/png")
                data = img["source"]["data"]
                messages_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{data}"},
                })
            else:
                messages_content.append(img)
    messages_content.append({"type": "text", "text": prompt})

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": messages_content}],
    )
    return response.choices[0].message.content.strip()
