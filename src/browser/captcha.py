"""CAPTCHA detection and solving.

The agent attempts to solve CAPTCHAs using its vision capabilities
(screenshot analysis) and browser interaction. Falls back to alerting
on Slack if it can't solve within 2 attempts.
"""

import asyncio
import base64

import anthropic
from playwright.async_api import Page

from src.browser.stealth import human_delay
from src.config import Config, SCREENSHOTS_DIR
from src.log import get_logger

log = get_logger("captcha")


async def detect_captcha(page: Page) -> str | None:
    """Detect if a CAPTCHA is present and identify its type.

    Returns the CAPTCHA type ('recaptcha', 'hcaptcha', 'custom', None).
    """
    captcha_type = await page.evaluate("""
        () => {
            if (document.querySelector('iframe[src*="recaptcha"]')) return 'recaptcha';
            if (document.querySelector('iframe[src*="hcaptcha"]')) return 'hcaptcha';
            if (document.querySelector('[class*="captcha"]')) return 'custom';
            if (document.querySelector('#captcha')) return 'custom';
            return null;
        }
    """)
    if captcha_type:
        log.info(f"CAPTCHA detected: {captcha_type}")
    return captcha_type


async def solve_captcha(
    page: Page,
    config: Config,
    max_attempts: int = 2,
) -> bool:
    """Attempt to solve a CAPTCHA.

    Strategy:
    1. Try clicking the checkbox (works for simple reCAPTCHA v2)
    2. If that fails, take a screenshot and use Claude vision to analyze
    3. Follow Claude's instructions to interact with the CAPTCHA

    Returns True if solved, False if manual intervention needed.
    """
    for attempt in range(max_attempts):
        log.info(f"CAPTCHA solve attempt {attempt + 1}/{max_attempts}")

        # Strategy 1: Simple checkbox click
        if await _try_checkbox_click(page):
            await asyncio.sleep(human_delay(2000, 4000))
            if not await detect_captcha(page):
                log.info("CAPTCHA solved via checkbox click")
                return True

        # Strategy 2: Vision-based solving
        solved = await _try_vision_solve(page, config)
        if solved:
            await asyncio.sleep(human_delay(2000, 4000))
            if not await detect_captcha(page):
                log.info("CAPTCHA solved via vision analysis")
                return True

        await asyncio.sleep(human_delay(1000, 2000))

    log.error("Failed to solve CAPTCHA after all attempts")
    return False


async def _try_checkbox_click(page: Page) -> bool:
    """Try to solve by clicking the CAPTCHA checkbox."""
    try:
        # reCAPTCHA checkbox
        frames = page.frames
        for frame in frames:
            try:
                checkbox = await frame.query_selector(
                    '.recaptcha-checkbox-border, '
                    '[role="checkbox"], '
                    '#recaptcha-anchor'
                )
                if checkbox:
                    await checkbox.click()
                    log.info("Clicked reCAPTCHA checkbox")
                    return True
            except Exception:
                continue

        # hCaptcha checkbox
        for frame in frames:
            try:
                checkbox = await frame.query_selector(
                    '#checkbox, .check'
                )
                if checkbox:
                    await checkbox.click()
                    log.info("Clicked hCaptcha checkbox")
                    return True
            except Exception:
                continue

    except Exception as e:
        log.warning(f"Checkbox click attempt failed: {e}")

    return False


async def _try_vision_solve(page: Page, config: Config) -> bool:
    """Use Claude's vision to analyze and solve the CAPTCHA.

    Takes a screenshot, sends it to Claude, and follows the instructions.
    """
    try:
        # Take screenshot
        screenshot_bytes = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        client = anthropic.Anthropic(api_key=config.anthropic_api_key)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "I'm trying to solve a CAPTCHA on this page. "
                                "What type of CAPTCHA is it? What do I need to do? "
                                "If it's a checkbox, say 'CLICK_CHECKBOX'. "
                                "If it's an image selection task (e.g., 'select all images with traffic lights'), "
                                "list the grid positions (1-9, left-to-right, top-to-bottom) I should click. "
                                "Format: 'CLICK_GRID: 1,4,7' "
                                "If you can't determine how to solve it, say 'CANNOT_SOLVE'."
                            ),
                        },
                    ],
                }
            ],
        )

        instruction = response.content[0].text.strip()
        log.info(f"Vision analysis: {instruction}")

        if "CANNOT_SOLVE" in instruction:
            return False

        if "CLICK_CHECKBOX" in instruction:
            return await _try_checkbox_click(page)

        if "CLICK_GRID" in instruction:
            # Parse grid positions
            import re
            match = re.search(r"CLICK_GRID:\s*([\d,\s]+)", instruction)
            if match:
                positions = [
                    int(p.strip()) for p in match.group(1).split(",") if p.strip()
                ]
                return await _click_grid_positions(page, positions)

        return False

    except Exception as e:
        log.error(f"Vision solve failed: {e}")
        return False


async def _click_grid_positions(page: Page, positions: list[int]) -> bool:
    """Click specific positions in a CAPTCHA grid.

    Positions are numbered 1-9 (or 1-16 for 4x4 grids),
    left-to-right, top-to-bottom.
    """
    try:
        # Find the CAPTCHA grid frame
        for frame in page.frames:
            grid = await frame.query_selector(
                '.rc-imageselect-table, .task-image-container, '
                '[class*="captcha-grid"]'
            )
            if not grid:
                continue

            bbox = await grid.bounding_box()
            if not bbox:
                continue

            # Determine grid size (3x3 or 4x4)
            cells = await frame.query_selector_all(
                'td.rc-imageselect-tile, .task-image, [class*="cell"]'
            )
            grid_size = 4 if len(cells) >= 16 else 3

            cell_w = bbox["width"] / grid_size
            cell_h = bbox["height"] / grid_size

            for pos in positions:
                row = (pos - 1) // grid_size
                col = (pos - 1) % grid_size
                x = bbox["x"] + col * cell_w + cell_w / 2
                y = bbox["y"] + row * cell_h + cell_h / 2

                await page.mouse.click(x, y)
                await asyncio.sleep(human_delay(300, 700))
                log.info(f"Clicked grid position {pos}")

            # Click verify/submit button
            verify_btn = await frame.query_selector(
                '#recaptcha-verify-button, button[type="submit"], '
                '.verify-button, .button-holder button'
            )
            if verify_btn:
                await asyncio.sleep(human_delay(500, 1000))
                await verify_btn.click()
                log.info("Clicked verify button")

            return True

    except Exception as e:
        log.error(f"Grid click failed: {e}")

    return False
