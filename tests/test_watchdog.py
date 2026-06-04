"""Tests for the self-audit / auto-heal watchdog checkers."""

import time

from src.watchdog import (
    Issue,
    check_cookies,
    check_db_initialized,
    check_screenshot_overflow,
    check_services_present,
    _heal,
)


class TestCheckers:
    def test_db_missing(self, tmp_path):
        issue = check_db_initialized(tmp_path / "nope.db")
        assert issue and issue.code == "db_missing" and issue.auto_fixable

    def test_db_present(self, tmp_path):
        p = tmp_path / "x.db"
        p.write_text("")
        assert check_db_initialized(p) is None

    def test_screenshot_overflow(self, tmp_path):
        for i in range(5):
            (tmp_path / f"s{i}.png").write_text("x")
        issue = check_screenshot_overflow(tmp_path, cap=3)
        assert issue and issue.code == "screenshot_overflow" and issue.auto_fixable

    def test_screenshot_under_cap(self, tmp_path):
        (tmp_path / "s.png").write_text("x")
        assert check_screenshot_overflow(tmp_path, cap=20) is None

    def test_cookies_missing_is_critical_unfixable(self, tmp_path):
        issue = check_cookies(tmp_path / "cookies.json")
        assert issue and issue.code == "cookies_missing"
        assert issue.severity == "critical" and issue.auto_fixable is False

    def test_cookies_fresh_ok(self, tmp_path):
        p = tmp_path / "cookies.json"
        p.write_text("[]")
        assert check_cookies(p, max_age_days=25) is None

    def test_cookies_stale_warns(self, tmp_path):
        p = tmp_path / "cookies.json"
        p.write_text("[]")
        old = time.time() - 40 * 86400
        import os
        os.utime(p, (old, old))
        issue = check_cookies(p, max_age_days=25)
        assert issue and issue.code == "cookies_stale" and issue.severity == "warning"

    def test_services_required_only_in_research_mode(self, tmp_path):
        missing = tmp_path / "services.yaml"
        assert check_services_present(missing, "off") is None
        issue = check_services_present(missing, "after_quota")
        assert issue and issue.code == "services_missing"


class TestHeal:
    def test_heal_screenshot_overflow(self, tmp_path, monkeypatch):
        import src.watchdog as wd
        called = {}
        monkeypatch.setattr(wd, "prune_screenshots", lambda keep=20: called.setdefault("keep", keep))
        assert _heal(Issue("screenshot_overflow", "warning", "x", True)) is True
        assert "keep" in called

    def test_heal_low_disk_prunes_aggressively(self, tmp_path, monkeypatch):
        import src.watchdog as wd
        captured = {}
        monkeypatch.setattr(wd, "prune_screenshots", lambda keep=20: captured.setdefault("keep", keep))
        assert _heal(Issue("low_disk", "critical", "x", True)) is True
        assert captured["keep"] == 5

    def test_heal_unknown_returns_false(self):
        assert _heal(Issue("cookies_missing", "critical", "x", False)) is False
