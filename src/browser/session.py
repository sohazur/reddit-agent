"""Browser session management for Reddit.

Handles login, cookie persistence, and session health checks.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.browser.stealth import (
    apply_stealth_scripts,
    get_stealth_context_options,
    get_stealth_launch_args,
    human_delay,
)
from src.config import Config, DATA_DIR, SCREENSHOTS_DIR
from src.log import get_logger

log = get_logger("session")

COOKIES_PATH = DATA_DIR / "cookies.json"


class RedditSession:
    """Manages a browser session for Reddit interaction."""

    def __init__(self, config: Config):
        self.config = config
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> "RedditSession":
        """Launch browser and establish Reddit session."""
        log.info("Starting browser session")
        self._playwright = await async_playwright().start()

        launch_args = get_stealth_launch_args()
        self._browser = await self._playwright.chromium.launch(**launch_args)

        context_options = get_stealth_context_options()

        # Load saved cookies if available
        if COOKIES_PATH.exists():
            try:
                cookies = json.loads(COOKIES_PATH.read_text())
                context_options["storage_state"] = {"cookies": cookies, "origins": []}
                log.info("Loaded saved cookies")
            except (json.JSONDecodeError, KeyError):
                log.warning("Failed to load cookies, starting fresh")

        self._context = await self._browser.new_context(**context_options)
        self._page = await self._context.new_page()
        await apply_stealth_scripts(self._page)

        # Check if we're already logged in
        if await self._is_logged_in():
            log.info("Session restored from cookies")
        else:
            log.info("Need to log in")
            await self._login()

        return self

    async def _is_logged_in(self) -> bool:
        """Check if the current session is authenticated."""
        try:
            await self._page.goto("https://www.reddit.com", wait_until="domcontentloaded")
            await asyncio.sleep(human_delay(1000, 2000))

            # Check for logged-in indicators
            # Reddit shows username in the header when logged in
            logged_in = await self._page.evaluate("""
                () => {
                    // Check for login button (indicates NOT logged in)
                    const loginBtn = document.querySelector('[data-testid="login-button"]')
                        || document.querySelector('a[href*="login"]');
                    return !loginBtn;
                }
            """)
            return logged_in
        except Exception as e:
            log.warning(f"Login check failed: {e}")
            return False

    async def _login(self) -> None:
        """Log in to Reddit via the browser."""
        log.info(f"Logging in as u/{self.config.reddit_account.username}")

        await self._page.goto(
            "https://www.reddit.com/login", wait_until="domcontentloaded"
        )
        await asyncio.sleep(human_delay(1500, 3000))

        # Fill username
        username_input = await self._page.wait_for_selector(
            'input[name="username"], #loginUsername', timeout=10000
        )
        await username_input.click()
        await asyncio.sleep(human_delay(200, 500))
        await self._type_human(username_input, self.config.reddit_account.username)
        await asyncio.sleep(human_delay(300, 800))

        # Fill password
        password_input = await self._page.wait_for_selector(
            'input[name="password"], #loginPassword', timeout=5000
        )
        await password_input.click()
        await asyncio.sleep(human_delay(200, 500))
        await self._type_human(password_input, self.config.reddit_account.password)
        await asyncio.sleep(human_delay(500, 1000))

        # Click login button
        login_btn = await self._page.wait_for_selector(
            'button[type="submit"], button:has-text("Log In")', timeout=5000
        )
        await login_btn.click()

        # Wait for navigation / potential CAPTCHA
        await asyncio.sleep(human_delay(3000, 5000))

        # Check for CAPTCHA
        if await self._detect_captcha():
            log.warning("CAPTCHA detected during login")
            await self._handle_captcha()

        # Verify login succeeded
        if await self._is_logged_in():
            log.info("Login successful")
            await self._save_cookies()
        else:
            log.error("Login failed — may need manual intervention")
            await self._screenshot("login_failed")
            raise RuntimeError("Reddit login failed")

    async def _detect_captcha(self) -> bool:
        """Check if a CAPTCHA is present on the page."""
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '[class*="captcha"]',
            '#captcha',
        ]
        for selector in captcha_selectors:
            try:
                element = await self._page.query_selector(selector)
                if element:
                    return True
            except Exception:
                continue
        return False

    async def _handle_captcha(self) -> None:
        """Attempt to solve a CAPTCHA using vision.

        Takes a screenshot, analyzes it, and tries to interact with the CAPTCHA.
        Falls back to alerting if it can't solve it.
        """
        log.info("Attempting to solve CAPTCHA")
        screenshot_path = await self._screenshot("captcha_challenge")

        # Try clicking through simple CAPTCHAs (checkbox type)
        try:
            checkbox = await self._page.query_selector(
                'iframe[src*="recaptcha"], iframe[src*="hcaptcha"]'
            )
            if checkbox:
                frame = await checkbox.content_frame()
                if frame:
                    check = await frame.query_selector(
                        '.recaptcha-checkbox, [id*="checkbox"]'
                    )
                    if check:
                        await check.click()
                        await asyncio.sleep(human_delay(2000, 4000))
                        log.info("Clicked CAPTCHA checkbox")
                        return
        except Exception as e:
            log.warning(f"CAPTCHA checkbox click failed: {e}")

        # If we can't solve it, take a screenshot and raise
        log.error(
            f"Cannot solve CAPTCHA automatically. Screenshot saved: {screenshot_path}"
        )
        # In the future, this could call a CAPTCHA solving service
        # or use Claude's vision to analyze the image
        raise RuntimeError("CAPTCHA requires manual intervention")

    async def _type_human(self, element, text: str) -> None:
        """Type text with human-like delays between keystrokes."""
        from src.browser.stealth import human_typing_delay

        for char in text:
            await element.type(char, delay=human_typing_delay() * 1000)

    async def _save_cookies(self) -> None:
        """Save current cookies for session reuse."""
        cookies = await self._context.cookies()
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
        log.info("Cookies saved")

    async def _screenshot(self, name: str) -> Path:
        """Take a screenshot for debugging."""
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOTS_DIR / f"{name}_{timestamp}.png"
        await self._page.screenshot(path=str(path))
        log.info(f"Screenshot saved: {path}")
        return path

    @property
    def page(self) -> Page:
        """Get the current page."""
        if not self._page:
            raise RuntimeError("Session not started")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get the browser context."""
        if not self._context:
            raise RuntimeError("Session not started")
        return self._context

    async def new_incognito_page(self) -> Page:
        """Create a new page in a fresh context (no cookies).

        Used for shadowban checking — view comments as a logged-out user.
        """
        context = await self._browser.new_context(
            **get_stealth_context_options()
        )
        page = await context.new_page()
        await apply_stealth_scripts(page)
        return page

    async def is_healthy(self) -> bool:
        """Quick health check — are we still logged in?"""
        try:
            return await self._is_logged_in()
        except Exception:
            return False

    async def close(self) -> None:
        """Clean up browser resources."""
        if self._context:
            await self._save_cookies()
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("Browser session closed")
