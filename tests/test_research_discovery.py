"""Tests for discovery pure-helpers (no browser/network)."""

from src.config import ServiceCatalog, Service
from src.research.discovery import (
    build_search_queries,
    normalize_sub_name,
    parse_subreddit_suggestions,
    reddit_search_url,
    subreddit_from_url,
)


def _catalog() -> ServiceCatalog:
    return ServiceCatalog(
        "ReachLLM", "reachllm.com", "AI visibility agency",
        services=[
            Service("technical_seo", "Tech SEO", ["traffic drops"],
                    ["traffic dropped", "core web vitals", "x"], "audit"),
            Service("geo_aeo", "GEO", ["not cited"], ["llms.txt", "rank in ChatGPT"], "opt"),
        ],
        audiences=["SMBs"],
    )


class TestNormalizeSubName:
    def test_strips_prefixes(self):
        assert normalize_sub_name("r/SEO") == "SEO"
        assert normalize_sub_name("/r/SEO/") == "SEO"
        assert normalize_sub_name("  SEO ") == "SEO"

    def test_rejects_garbage(self):
        assert normalize_sub_name("not a sub name") is None
        assert normalize_sub_name("") is None
        assert normalize_sub_name("a") is None  # too short


class TestParseSuggestions:
    def test_parses_array(self):
        text = '[{"name": "r/SEO", "relevance": 9, "rationale": "buyers here"}, {"name": "smallbusiness", "relevance": 6}]'
        out = parse_subreddit_suggestions(text)
        assert [o["name"] for o in out] == ["SEO", "smallbusiness"]
        assert out[0]["relevance"] == 9

    def test_dedups_case_insensitive(self):
        text = '[{"name": "SEO", "relevance": 9}, {"name": "seo", "relevance": 5}]'
        out = parse_subreddit_suggestions(text)
        assert len(out) == 1

    def test_fenced(self):
        text = '```json\n[{"name": "SEO", "relevance": 8}]\n```'
        assert parse_subreddit_suggestions(text)[0]["name"] == "SEO"

    def test_clamps_relevance(self):
        text = '[{"name": "SEO", "relevance": 99}]'
        assert parse_subreddit_suggestions(text)[0]["relevance"] == 10

    def test_garbage(self):
        assert parse_subreddit_suggestions("nope") == []


class TestSearchQueries:
    def test_builds_distinct_queries(self):
        qs = build_search_queries(_catalog())
        assert "traffic dropped" in qs
        assert "llms.txt" in qs
        # The 1-char signal "x" is too short and must be dropped.
        assert "x" not in qs

    def test_respects_limit(self):
        assert len(build_search_queries(_catalog(), limit=2)) == 2


class TestUrls:
    def test_search_url_encodes(self):
        url = reddit_search_url("core web vitals")
        assert "core+web+vitals" in url
        assert url.startswith("https://www.reddit.com/search/")

    def test_subreddit_from_url(self):
        assert subreddit_from_url("https://www.reddit.com/r/SEO/comments/abc/x/") == "SEO"
        assert subreddit_from_url("https://example.com/none") == ""
