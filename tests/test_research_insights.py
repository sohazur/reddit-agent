"""Tests for the research insights renderer."""

from src.research.insights import render_insights, _cluster_by_subreddit


def test_cluster_by_subreddit_counts_and_sorts():
    opps = [
        {"subreddit": "SEO"}, {"subreddit": "SEO"}, {"subreddit": "smallbusiness"},
    ]
    clusters = _cluster_by_subreddit(opps)
    assert clusters[0] == ("SEO", 2)
    assert ("smallbusiness", 1) in clusters


def test_render_includes_pipeline_and_clusters():
    opps = [{"subreddit": "SEO"}, {"subreddit": "SEO"}]
    viral = [{"score": 300, "comment_count": 40, "subreddit": "SEO", "title": "Hot"}]
    counts = {"total": 5, "new": 2, "pushed": 3}
    md = render_insights(opps, viral, counts)
    assert "Total tracked: 5" in md
    assert "Pushed to platform: 3" in md
    assert "r/SEO: 2" in md
    assert "Hot" in md


def test_render_empty_states():
    md = render_insights([], [], {"total": 0})
    assert "(none yet)" in md
    assert "no high-traction posts" in md.lower()
