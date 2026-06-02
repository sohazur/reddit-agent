"""Tests for the per-account persona."""

from unittest.mock import patch

import pytest

import src.intelligence.persona as persona_mod
from src.intelligence.persona import (
    load_persona,
    persona_prompt,
    save_persona,
)


@pytest.fixture
def persona_path(tmp_path):
    path = tmp_path / "persona.yaml"
    with patch.object(persona_mod, "PERSONA_PATH", path):
        yield path


def test_load_missing_returns_empty(persona_path):
    assert load_persona() == {}


def test_prompt_empty_when_no_persona(persona_path):
    assert persona_prompt() == ""


def test_save_and_load_round_trip(persona_path):
    save_persona({
        "voice": "casual and blunt",
        "interests": ["cycling", "self-hosting"],
        "backstory": "works in devops, lurks a lot",
        "quirks": ["lowercase", "trails off with ..."],
    })
    loaded = load_persona()
    assert loaded["voice"] == "casual and blunt"
    assert "cycling" in loaded["interests"]


def test_save_drops_unknown_fields(persona_path):
    save_persona({"voice": "x", "active_hours": "9-5", "evil": True})
    loaded = load_persona()
    assert "active_hours" not in loaded  # dropped (YAGNI per review)
    assert "evil" not in loaded
    assert loaded["voice"] == "x"


def test_prompt_renders_fields(persona_path):
    save_persona({
        "voice": "dry humor",
        "interests": ["coffee"],
        "backstory": "barista turned dev",
        "quirks": ["no caps"],
    })
    out = persona_prompt()
    assert "dry humor" in out
    assert "coffee" in out
    assert "barista" in out
    assert "ONE consistent person" in out


def test_prompt_handles_string_lists(persona_path):
    # interests/quirks given as plain strings, not lists.
    save_persona({"voice": "v", "interests": "coffee, tea", "quirks": "terse"})
    out = persona_prompt()
    assert "coffee, tea" in out
