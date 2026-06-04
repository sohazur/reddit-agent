"""Tests for RedditSession.navigate() transient-403 recovery."""

import pytest

import src.browser.session as sess
from src.browser.session import NetworkBlockedError, RedditSession, _is_network_block


BLOCK_TEXT = "You've been blocked by network security. File a ticket"
OK_TEXT = "r/SEO hot posts ..."


class TestIsNetworkBlock:
    def test_403_with_banner(self):
        assert _is_network_block(403, BLOCK_TEXT) is True

    def test_200_with_banner(self):
        # Some block responses come back 200 with the wall in the body.
        assert _is_network_block(200, BLOCK_TEXT) is True

    def test_clean_page(self):
        assert _is_network_block(200, OK_TEXT) is False

    def test_403_without_banner_not_block(self):
        # A plain 403 that isn't the security wall (e.g. private sub) isn't ours.
        assert _is_network_block(403, "This community is private") is False


class _FakeResp:
    def __init__(self, status):
        self.status = status


class _FakePage:
    """A page whose goto returns a scripted sequence of (status, body) pairs."""

    def __init__(self, sequence):
        self._seq = list(sequence)
        self._cur = None
        self.goto_calls = 0

    async def goto(self, url, wait_until="domcontentloaded"):
        status, body = self._seq[min(self.goto_calls, len(self._seq) - 1)]
        self._cur = body
        self.goto_calls += 1
        return _FakeResp(status)

    async def evaluate(self, _fn):
        return self._cur


def _session_with(page):
    s = RedditSession.__new__(RedditSession)  # bypass __init__/browser launch
    s._page = page
    return s


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(*_a, **_k):
        return None
    monkeypatch.setattr(sess.asyncio, "sleep", _instant)
    monkeypatch.setattr(sess, "human_delay", lambda *a, **k: 0.0)


async def test_recovers_after_one_block():
    # Blocked once, then a clean page — navigate should return without raising.
    page = _FakePage([(403, BLOCK_TEXT), (200, OK_TEXT)])
    s = _session_with(page)
    resp = await s.navigate("https://www.reddit.com/r/SEO/hot/")
    assert resp.status == 200
    assert page.goto_calls == 2


async def test_succeeds_first_try():
    page = _FakePage([(200, OK_TEXT)])
    s = _session_with(page)
    resp = await s.navigate("https://www.reddit.com/r/SEO/hot/")
    assert resp.status == 200
    assert page.goto_calls == 1


async def test_raises_on_persistent_block():
    # Always blocked — after retries, navigate raises NetworkBlockedError.
    page = _FakePage([(403, BLOCK_TEXT)])
    s = _session_with(page)
    with pytest.raises(NetworkBlockedError):
        await s.navigate("https://www.reddit.com/search/?q=x", retries=2)
    # initial + 2 retries = 3 goto attempts
    assert page.goto_calls == 3
