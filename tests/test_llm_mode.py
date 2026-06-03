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
