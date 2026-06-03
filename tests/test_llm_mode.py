"""Tests for LLM provider detection, incl. agent-provided handoff."""

import os
from unittest.mock import patch

import src.llm as llm


def test_direct_key_used_when_present():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-real", "LLM_MODE": ""}, clear=True):
        provider, key = llm._detect_provider()
        assert provider == "anthropic"
        assert key == "sk-ant-real"


def test_openai_key_used_when_present():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real", "LLM_MODE": ""}, clear=True):
        provider, key = llm._detect_provider()
        assert provider == "openai"


def test_explicit_agent_mode_overrides_keys():
    # Even with a key present, LLM_MODE=agent-provided routes to the host agent.
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant", "LLM_MODE": "agent-provided"}, clear=True):
        provider, key = llm._detect_provider()
        assert provider == "agent"
        assert key == ""


def test_falls_back_to_agent_when_no_key():
    # No key anywhere → agent-provided handoff (no longer raises).
    with patch.dict(os.environ, {"LLM_MODE": ""}, clear=True):
        # Point rc/openclaw lookups at nonexistent paths via HOME isolation.
        with patch.object(os.path, "exists", return_value=False):
            provider, key = llm._detect_provider()
            assert provider == "agent"
            assert key == ""


def test_agent_handoff_rejects_stale_response(tmp_path, monkeypatch):
    """A response whose id != the current request's id must be ignored, not
    returned (prevents posting a stale/mismatched LLM answer)."""
    import json, threading, time
    import src.config as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    # also patch the reference llm.py imports via the module's DATA_DIR usage
    req = tmp_path / ".llm-request.json"
    resp = tmp_path / ".llm-response.json"

    # Pre-stage a STALE response with a wrong id before the call starts.
    resp.write_text(json.dumps({"id": "WRONG", "response": "stale answer"}))

    result = {}
    def run():
        result["val"] = llm._call_agent("hi", 50, None)

    t = threading.Thread(target=run)
    t.start()
    # Give the call a moment to clear the stale resp + write its request.
    time.sleep(2)
    # Read the real request id and answer it correctly.
    real_id = json.loads(req.read_text())["id"]
    # Atomic-ish write of the correct response.
    resp.write_text(json.dumps({"id": real_id, "response": "correct answer"}))
    t.join(timeout=10)

    assert result.get("val") == "correct answer"
