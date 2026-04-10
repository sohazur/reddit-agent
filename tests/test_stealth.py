"""Tests for the stealth/anti-detection module."""

from src.browser.stealth import (
    USER_AGENTS,
    VIEWPORTS,
    get_stealth_context_options,
    get_stealth_launch_args,
    human_delay,
    human_typing_delay,
)


class TestStealthConfig:
    def test_launch_args_headless(self):
        """Launch args should default to headless."""
        args = get_stealth_launch_args()
        assert args["headless"] is True

    def test_launch_args_disable_automation(self):
        """Should disable automation detection flags."""
        args = get_stealth_launch_args()
        assert any("AutomationControlled" in a for a in args["args"])

    def test_context_has_user_agent(self):
        """Context should include a real user agent."""
        opts = get_stealth_context_options()
        assert opts["user_agent"] in USER_AGENTS

    def test_context_has_viewport(self):
        """Context should include a common viewport."""
        opts = get_stealth_context_options()
        assert opts["viewport"] in VIEWPORTS

    def test_context_has_locale(self):
        """Context should set locale."""
        opts = get_stealth_context_options()
        assert opts["locale"] == "en-US"


class TestHumanDelays:
    def test_human_delay_range(self):
        """Human delay should be within expected range."""
        for _ in range(100):
            delay = human_delay(500, 2000)
            # Base range is 0.5-2.0s, with 10% chance of 1.5-3x multiplier
            # So max is roughly 2.0 * 3.0 = 6.0s
            assert 0.5 <= delay <= 7.0

    def test_typing_delay_range(self):
        """Typing delay should be between 30-120ms."""
        for _ in range(100):
            delay = human_typing_delay()
            assert 0.03 <= delay <= 0.12

    def test_delays_vary(self):
        """Delays should not be constant."""
        delays = {human_delay() for _ in range(10)}
        assert len(delays) > 1, "Delays should vary between calls"
