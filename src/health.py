"""Health check: verify all dependencies and configuration.

Usage:
    python -m src.health
"""

import os
import sys
from pathlib import Path

from src.config import DATA_DIR, PROMPTS_DIR


def check_env_vars() -> list[str]:
    """Check required environment variables."""
    issues = []
    required = ["REDDIT_USERNAME", "REDDIT_PASSWORD", "ANTHROPIC_API_KEY"]
    for var in required:
        if not os.environ.get(var):
            issues.append(f"Missing env var: {var}")
    return issues


def check_files() -> list[str]:
    """Check required files exist."""
    issues = []
    subreddits_yaml = DATA_DIR / "subreddits.yaml"
    if not subreddits_yaml.exists():
        issues.append(f"Missing: {subreddits_yaml}")

    for prompt in ["evaluate_thread", "generate_comment", "quality_check", "subreddit_intel"]:
        path = PROMPTS_DIR / f"{prompt}.md"
        if not path.exists():
            issues.append(f"Missing prompt: {path}")

    return issues


def check_db() -> list[str]:
    """Check database is initialized."""
    issues = []
    db_path = DATA_DIR / "reddit.db"
    if not db_path.exists():
        issues.append("Database not initialized. Run: python -c 'from src.db import init_db; init_db()'")
    return issues


def check_playwright() -> list[str]:
    """Check Playwright and Chromium are installed."""
    issues = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        issues.append(f"Playwright/Chromium issue: {e}")
    return issues


def main():
    print("Reddit Agent — Health Check")
    print("=" * 40)

    all_issues = []

    print("\n1. Environment variables...")
    issues = check_env_vars()
    all_issues.extend(issues)
    print(f"   {'PASS' if not issues else 'FAIL'}")
    for i in issues:
        print(f"   - {i}")

    print("\n2. Required files...")
    issues = check_files()
    all_issues.extend(issues)
    print(f"   {'PASS' if not issues else 'FAIL'}")
    for i in issues:
        print(f"   - {i}")

    print("\n3. Database...")
    issues = check_db()
    all_issues.extend(issues)
    print(f"   {'PASS' if not issues else 'FAIL'}")
    for i in issues:
        print(f"   - {i}")

    print("\n4. Playwright/Chromium...")
    issues = check_playwright()
    all_issues.extend(issues)
    print(f"   {'PASS' if not issues else 'FAIL'}")
    for i in issues:
        print(f"   - {i}")

    print("\n" + "=" * 40)
    if all_issues:
        print(f"ISSUES: {len(all_issues)}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
