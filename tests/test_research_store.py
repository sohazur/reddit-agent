"""Tests for the Research-mode persistence layer."""

import uuid

import pytest

import src.db as db_module
from src.db import init_db
from src.research import store


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_path = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = db_path
    init_db(db_path)
    yield db_path
    db_module.DB_PATH = original


class TestOpportunityId:
    def test_stable_and_normalized(self):
        """Same post (querystring/trailing slash/case differences) → same id."""
        a = store.opportunity_id("https://reddit.com/r/SEO/comments/abc/")
        b = store.opportunity_id("https://reddit.com/r/seo/comments/abc?utm=1")
        assert a == b

    def test_different_posts_differ(self):
        assert store.opportunity_id("https://x/1") != store.opportunity_id("https://x/2")


class TestOpportunities:
    def test_record_and_fetch(self):
        url = "https://reddit.com/r/SEO/comments/abc"
        oid = store.record_opportunity(
            url=url, subreddit="SEO", thread_id="abc", title="Help my traffic dropped",
            author="bob", problem_summary="traffic crash", matched_services=["technical_seo"],
            suggested_angle="offer audit", priority=8, confidence=0.9,
        )
        assert store.opportunity_exists(oid)
        opps = store.get_opportunities(status="new")
        assert len(opps) == 1
        assert opps[0]["matched_services"] == ["technical_seo"]
        assert opps[0]["priority"] == 8

    def test_dedup_on_reinsert(self):
        url = "https://reddit.com/r/SEO/comments/abc"
        for _ in range(3):
            store.record_opportunity(
                url=url, subreddit="SEO", thread_id="abc", title="t", author="a",
                problem_summary="p", matched_services=[], suggested_angle="x",
                priority=7, confidence=0.5,
            )
        assert store.count_opportunities()["total"] == 1

    def test_ordering_by_priority(self):
        for i, pri in enumerate([3, 9, 6]):
            store.record_opportunity(
                url=f"https://x/{i}", subreddit="SEO", thread_id=str(i), title="t",
                author="a", problem_summary="p", matched_services=[],
                suggested_angle="x", priority=pri, confidence=0.5,
            )
        opps = store.get_opportunities()
        assert [o["priority"] for o in opps] == [9, 6, 3]

    def test_mark_pushed(self):
        oid = store.record_opportunity(
            url="https://x/1", subreddit="SEO", thread_id="1", title="t", author="a",
            problem_summary="p", matched_services=[], suggested_angle="x",
            priority=7, confidence=0.5,
        )
        store.mark_opportunities_pushed([oid])
        assert store.count_opportunities().get("pushed") == 1
        assert store.get_opportunities(status="new") == []


class TestResearchSubreddits:
    def test_upsert_and_relevance_max(self):
        store.upsert_research_subreddit("SEO", "llm", relevance=5)
        store.upsert_research_subreddit("SEO", "llm", relevance=8)
        subs = store.get_research_subreddits()
        assert len(subs) == 1
        assert subs[0]["relevance"] == 8

    def test_skip_not_returned(self):
        store.upsert_research_subreddit("Spam", "llm", relevance=9, status="skip")
        assert store.get_research_subreddits() == []

    def test_scanned_marks_active(self):
        store.upsert_research_subreddit("SEO", "llm", relevance=5)
        store.mark_subreddit_scanned("SEO")
        assert store.subreddit_known("SEO")


class TestViral:
    def test_record_keeps_best_score(self):
        store.record_viral_observation("t1", "SEO", "title", "https://x/1", 50, 10)
        store.record_viral_observation("t1", "SEO", "title", "https://x/1", 30, 99)
        top = store.get_top_viral(min_score=1)
        assert len(top) == 1
        assert top[0]["score"] == 50  # kept the higher score
        assert top[0]["comment_count"] == 99  # kept the higher comment count

    def test_min_score_filter(self):
        store.record_viral_observation("t1", "SEO", "t", "https://x/1", 10, 1)
        assert store.get_top_viral(min_score=50) == []
