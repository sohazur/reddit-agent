"""Tests for configuration loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import load_config, load_subreddits, load_prompt


class TestLoadSubreddits:
    def test_loads_configured_subreddits(self):
        """Should load subreddits from the YAML config."""
        subs = load_subreddits()
        assert len(subs) >= 1
        assert subs[0].name == "SEO"
        assert len(subs[0].keywords) > 0
        assert subs[0].max_daily_comments > 0

    def test_subreddit_has_tone(self):
        """Each subreddit should have tone guidance."""
        subs = load_subreddits()
        for sub in subs:
            assert sub.tone, f"r/{sub.name} is missing tone guidance"


class TestLoadConfig:
    def test_requires_env_vars(self):
        """Should raise when required env vars are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="REDDIT_USERNAME"):
                load_config()

    def test_loads_with_env_vars(self):
        """Should load config when all required vars are set."""
        env = {
            "REDDIT_USERNAME": "test",
            "REDDIT_PASSWORD": "test",
            "ANTHROPIC_API_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.reddit_account.username == "test"
            assert config.anthropic_api_key == "sk-test"
            assert config.max_comments_per_day == 5  # default

    def test_loads_without_api_key(self):
        """Should load config even without API key (OpenClaw provides it)."""
        env = {
            "REDDIT_USERNAME": "test",
            "REDDIT_PASSWORD": "test",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.reddit_account.username == "test"
            assert config.anthropic_api_key == ""  # empty, agent provides

    def test_custom_limits(self):
        """Should respect custom limits from env vars."""
        env = {
            "REDDIT_USERNAME": "test",
            "REDDIT_PASSWORD": "test",
            "ANTHROPIC_API_KEY": "sk-test",
            "MAX_COMMENTS_PER_DAY": "10",
            "MIN_COMMENT_INTERVAL_MINUTES": "30",
            "QUALITY_THRESHOLD": "8",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.max_comments_per_day == 10
            assert config.min_comment_interval_minutes == 30
            assert config.quality_threshold == 8


class TestLoadPrompt:
    def test_loads_existing_prompt(self):
        """Should load a prompt template."""
        prompt = load_prompt(
            "evaluate_thread",
            subreddit_name="SEO",
            subreddit_tone="Technical",
            subreddit_notes="Be subtle",
            thread_title="Test",
            thread_body="Body",
            thread_score="10",
            thread_comment_count="5",
            thread_comments="Comment 1",
        )
        assert "SEO" in prompt
        assert "Technical" in prompt
        assert "Test" in prompt

    def test_raises_for_missing_prompt(self):
        """Should raise for nonexistent prompt template."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")
