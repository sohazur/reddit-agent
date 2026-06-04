"""Tests for opportunity report rendering + push payload + sink no-op."""

import os
import uuid
from unittest.mock import patch

import pytest

import src.db as db_module
from src.config import ServiceCatalog, Service, load_config
from src.db import init_db
from src.research import store
from src.research.report import build_payload, render_markdown


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_path = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = db_path
    init_db(db_path)
    yield db_path
    db_module.DB_PATH = original


def _catalog() -> ServiceCatalog:
    return ServiceCatalog(
        "ReachLLM", "reachllm.com", "AI visibility agency",
        services=[Service("technical_seo", "Technical SEO", ["x"], ["y"], "We audit.")],
        audiences=["SMBs"],
    )


def _opp(**kw):
    base = {
        "id": "abc", "url": "https://reddit.com/r/SEO/comments/1",
        "title": "Traffic dropped 40%", "subreddit": "SEO", "author": "bob",
        "priority": 8, "confidence": 0.9, "problem_summary": "traffic crash",
        "matched_services": ["technical_seo"], "suggested_angle": "offer audit",
        "found_at": "2026-06-04T00:00:00", "status": "new",
    }
    base.update(kw)
    return base


class TestRenderMarkdown:
    def test_includes_core_fields(self):
        md = render_markdown([_opp()], _catalog())
        assert "Traffic dropped 40%" in md
        assert "8/10" in md
        assert "r/SEO" in md
        assert "Technical SEO" in md
        assert "We audit." in md  # pitch line expanded

    def test_empty_state(self):
        md = render_markdown([], _catalog())
        assert "still scanning" in md.lower()

    def test_viral_section(self):
        viral = [{"title": "Big thread", "url": "https://x", "score": 500,
                  "comment_count": 99, "subreddit": "SEO"}]
        md = render_markdown([_opp()], _catalog(), viral)
        assert "getting traction" in md.lower()
        assert "500 upvotes" in md


class TestBuildPayload:
    def test_shape(self):
        payload = build_payload([_opp()], _catalog())
        assert payload["company"] == "ReachLLM"
        assert payload["count"] == 1
        assert payload["opportunities"][0]["matched_services"] == ["technical_seo"]


class TestSinkNoOp:
    def test_push_is_noop_without_url(self):
        from src.integrations.reachllm import push_new_opportunities
        env = {"REDDIT_USERNAME": "t", "REDDIT_PASSWORD": "t"}
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
        store.record_opportunity(
            url="https://x/1", subreddit="SEO", thread_id="1", title="t", author="a",
            problem_summary="p", matched_services=["technical_seo"],
            suggested_angle="x", priority=8, confidence=0.5,
        )
        result = push_new_opportunities(config)
        assert result["skipped"] is True
        assert result["pushed"] == 0
        # Nothing should have been marked pushed.
        assert store.count_opportunities().get("new") == 1
