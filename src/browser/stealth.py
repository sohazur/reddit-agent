"""Anti-detection configuration for the browser.

Uses Playwright launch options to minimize bot detection fingerprints.
For stronger stealth, consider nodriver or camoufox as drop-in replacements.
"""

import random

# Common user agents for Chrome on macOS/Windows
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Common viewport sizes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]

# Timezones to match user agents
TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "America/Denver",
    "Europe/London",
]


def get_stealth_launch_args() -> dict:
    """Get Playwright launch arguments that minimize detection."""
    viewport = random.choice(VIEWPORTS)

    return {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={viewport['width']},{viewport['height']}",
        ],
    }


def get_stealth_context_options() -> dict:
    """Get browser context options for stealth."""
    viewport = random.choice(VIEWPORTS)
    user_agent = random.choice(USER_AGENTS)
    timezone = random.choice(TIMEZONES)

    return {
        "user_agent": user_agent,
        "viewport": viewport,
        "locale": "en-US",
        "timezone_id": timezone,
        "permissions": ["geolocation"],
        "geolocation": {"longitude": -73.935242, "latitude": 40.730610},
        "color_scheme": "light",
        "java_script_enabled": True,
    }


async def apply_stealth_scripts(page) -> None:
    """Inject JavaScript to mask automation indicators.

    This overrides common detection vectors:
    - navigator.webdriver
    - chrome.runtime
    - Permissions API
    - Plugin/language enumeration
    """
    await page.add_init_script("""
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // Mock chrome runtime
        window.chrome = {
            runtime: {},
        };

        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Mock hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
        });

        // Mock device memory
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
        });
    """)


def human_delay(min_ms: int = 500, max_ms: int = 2000) -> float:
    """Generate a human-like delay in seconds.

    Uses a slightly skewed distribution to mimic real typing/clicking patterns.
    """
    # Skew toward the lower end but occasionally be slow
    base = random.uniform(min_ms, max_ms)
    # 10% chance of a longer "thinking" pause
    if random.random() < 0.1:
        base *= random.uniform(1.5, 3.0)
    return base / 1000.0


def human_typing_delay() -> float:
    """Delay between keystrokes when typing."""
    return random.uniform(0.03, 0.12)
