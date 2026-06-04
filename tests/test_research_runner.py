"""End-to-end wiring test for a research pass (browser + LLM stubbed)."""

import os
import uuid
from unittest.mock import patch

import pytest

import src.db as db_module
import src.research.runner as runner
import src.scanner.subreddit as scanner
from src.config import load_config
from src.db import init_db
from src.research import store
from src.research.classifier import Opportunity
from src.scanner.subreddit import DiscoveredThread


@pytest.fixture(autouse=True)
def isolated(tmp_path):
    db_path = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = db_path
    init_db(db_path)
    env = {
        "REDDIT_USERNAME": "t", "REDDIT_PASSWORD": "t",
        "RESEARCH_MODE": "only", "RESEARCH_MAX_SUBREDDITS": "1",
        "RESEARCH_MAX_THREADS_PER_SUB": "1", "RESEARCH_MIN_PRIORITY": "6",
    }
    with patch.dict(os.environ, env, clear=True):
        yield
    db_module.DB_PATH = original


async def _fake_scan(session, sub_cfg, limit=10):
    return [DiscoveredThread(
        id="t3abc", subreddit=sub_cfg.name, title="Traffic dropped 40% after AI overviews",
        body="", url="https://www.reddit.com/r/SEO/comments/abc/x/",
        score=120, comment_count=15, top_comments=[],
    )]


async def _fake_read(session, url, max_comments=10):
    return {"title": "Traffic dropped", "body": "site lost half its traffic", "comments": []}


async def _fake_classify(config, catalog, subreddit, thread_title, thread_body, thread_comments):
    return Opportunity(
        is_opportunity=True, priority=8, confidence=0.9,
        matched_services=["technical_seo"], problem_summary="traffic crash",
        suggested_angle="offer a technical audit",
    )


async def _no_candidates_search(session, config, catalog, per_query=10):
    return []


@pytest.mark.asyncio
async def test_research_pass_records_opportunity(monkeypatch):
    config = load_config()

    # Stub discovery (no network/LLM) and browser/LLM touchpoints.
    monkeypatch.setattr(runner, "suggest_subreddits_via_llm", lambda c, cat: [])
    monkeypatch.setattr(runner, "discover_subreddits_via_web", lambda c, cat: [])
    monkeypatch.setattr(runner, "discover_threads_via_search", _no_candidates_search)
    monkeypatch.setattr(runner, "classify_opportunity", _fake_classify)
    monkeypatch.setattr(scanner, "scan_subreddit", _fake_scan)
    monkeypatch.setattr(scanner, "read_thread_details", _fake_read)
    # Don't write real files / push during the test.
    monkeypatch.setattr(runner, "write_outputs", lambda cat: {})
    monkeypatch.setattr(runner, "update_research_insights", lambda: None)

    # Give the pass one subreddit to scan.
    from src.config import SubredditConfig
    config.subreddits = [SubredditConfig("SEO", [], 0, "")]

    results = await runner.run_research_pass(config, session=object())

    assert results["opportunities_new"] == 1
    assert results["viral_seen"] == 1  # score 120 >= 100
    opps = store.get_opportunities(status="new")
    assert len(opps) == 1
    assert opps[0]["priority"] == 8
    assert opps[0]["matched_services"] == ["technical_seo"]


@pytest.mark.asyncio
async def test_low_priority_not_recorded(monkeypatch):
    config = load_config()

    async def _low(config, catalog, subreddit, thread_title, thread_body, thread_comments):
        return Opportunity(True, 3, 0.4, ["technical_seo"], "minor", "x")

    monkeypatch.setattr(runner, "suggest_subreddits_via_llm", lambda c, cat: [])
    monkeypatch.setattr(runner, "discover_subreddits_via_web", lambda c, cat: [])
    monkeypatch.setattr(runner, "discover_threads_via_search", _no_candidates_search)
    monkeypatch.setattr(runner, "classify_opportunity", _low)
    monkeypatch.setattr(scanner, "scan_subreddit", _fake_scan)
    monkeypatch.setattr(scanner, "read_thread_details", _fake_read)
    monkeypatch.setattr(runner, "write_outputs", lambda cat: {})
    monkeypatch.setattr(runner, "update_research_insights", lambda: None)

    from src.config import SubredditConfig
    config.subreddits = [SubredditConfig("SEO", [], 0, "")]

    results = await runner.run_research_pass(config, session=object())
    assert results["opportunities_new"] == 0
    assert store.get_opportunities(status="new") == []
