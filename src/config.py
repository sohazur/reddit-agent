"""Configuration loaded from environment variables and YAML files."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
DB_PATH = DATA_DIR / "reddit.db"
LEARNINGS_PATH = DATA_DIR / "learnings.md"
SUBREDDIT_REPORTS_DIR = DATA_DIR / "subreddit_reports"


@dataclass
class RedditAccount:
    username: str
    password: str


@dataclass
class SubredditConfig:
    name: str
    keywords: list[str]
    max_daily_comments: int
    tone: str
    notes: str = ""
    min_karma: int = 0


@dataclass
class Config:
    # Reddit
    reddit_account: RedditAccount

    # Anthropic
    anthropic_api_key: str

    # Slack
    slack_webhook_url: str

    # Cadence
    max_comments_per_day: int
    min_comment_interval_minutes: int
    quality_threshold: int
    cycle_interval_hours: int

    # Subreddits
    subreddits: list[SubredditConfig] = field(default_factory=list)

    # Paths
    ai_marketing_tracker_path: Path | None = None

    # Logging
    log_level: str = "INFO"
    screenshot_on_error: bool = True


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Required environment variable {key} is not set")
    return val


def _get_api_key() -> str:
    """Get an LLM API key from environment.

    Checks multiple sources in order:
    1. ANTHROPIC_API_KEY from .env or environment
    2. OPENAI_API_KEY as fallback (for OpenClaw instances using OpenAI)
    3. "agent-provided" placeholder (OpenClaw agent handles LLM calls)
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and key != "agent-provided":
        return key

    # OpenClaw may have the key in its shell env
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key

    return ""


def load_subreddits() -> list[SubredditConfig]:
    """Load subreddit configuration from YAML."""
    config_path = DATA_DIR / "subreddits.yaml"
    if not config_path.exists():
        return []

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return [
        SubredditConfig(
            name=s["name"],
            keywords=s.get("keywords", []),
            max_daily_comments=s.get("max_daily_comments", 2),
            tone=s.get("tone", ""),
            notes=s.get("notes", ""),
            min_karma=s.get("min_karma", 0),
        )
        for s in raw.get("subreddits", [])
    ]


def load_config() -> Config:
    """Load full configuration from environment and YAML files."""
    tracker_path = os.environ.get("AI_MARKETING_TRACKER_PATH")

    return Config(
        reddit_account=RedditAccount(
            username=_require_env("REDDIT_USERNAME"),
            password=_require_env("REDDIT_PASSWORD"),
        ),
        anthropic_api_key=_get_api_key(),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
        max_comments_per_day=int(os.environ.get("MAX_COMMENTS_PER_DAY", "5")),
        min_comment_interval_minutes=int(
            os.environ.get("MIN_COMMENT_INTERVAL_MINUTES", "20")
        ),
        quality_threshold=int(os.environ.get("QUALITY_THRESHOLD", "7")),
        cycle_interval_hours=int(os.environ.get("CYCLE_INTERVAL_HOURS", "2")),
        subreddits=load_subreddits(),
        ai_marketing_tracker_path=Path(tracker_path) if tracker_path else None,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        screenshot_on_error=os.environ.get("SCREENSHOT_ON_ERROR", "true").lower()
        == "true",
    )


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template from prompts/ and substitute variables."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    template = path.read_text()
    for key, value in kwargs.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template
