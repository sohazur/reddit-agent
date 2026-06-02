"""Compliance gate: enforce subreddit rules before posting.

This is the safety floor that keeps the account alive. It has two layers:

1. DETERMINISTIC GATE (this module, pure Python, no LLM): checks objective
   rules — links, account karma, account age, banned phrases, self-promotion.
   A deterministic BLOCK is TERMINAL: it skips regeneration, because
   regenerating text cannot fix low karma or a too-young account. Every
   uncertain decision FAILS CLOSED (block, don't post).

2. FUZZY JUDGE (compliance_judge, LLM): checks subjective rules — "stay on
   topic", "be respectful". The judge may only ADD blocks, never override a
   deterministic decision. A judge timeout/error counts as a BLOCK.

Final decision = AND of all gates: any block wins.
"""

import re
from dataclasses import dataclass, field

from src.log import get_logger

log = get_logger("compliance")

# Bare-domain TLD: ANY 2-24 char alphabetic TLD, not a fixed list. Enumerating
# TLDs fails open — the LLM can emit any TLD (.link, .shop, .online, .click, …)
# and a link would slip through a no-links subreddit. We match the SHAPE of a
# domain and fail closed (over-block beats letting a banned link post).
_TLD = r"[a-z]{2,24}"

# Tiny denylist of strings that look like "word.tld" but are normal prose, so we
# don't block every comment that says "e.g." or "i.e.". These are the only
# common English abbreviations that collide with the domain shape.
_NOT_LINKS = re.compile(r"\b(?:e\.g|i\.e|etc|vs|a\.m|p\.m)\.", re.IGNORECASE)


def _strip_prose_abbreviations(text: str) -> str:
    """Blank out common abbreviations so they don't read as bare domains."""
    return _NOT_LINKS.sub(" ", text)


# Real links: "http(s)://...", "www.example.com", "example.com".
_URL_RE = re.compile(
    rf"""(
        https?://\S+                       # http(s):// links
      | www\.\S+                           # www. links
      | \b[a-z0-9][\w-]*\.{_TLD}\b         # bare domain example.<tld>
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Obfuscated links: "example dot com", "example[.]com", "example (dot) com".
_OBFUSCATED_RE = re.compile(
    rf"""\b[a-z0-9][\w-]*
        \s*(?:\[\s*\.\s*\]|\(\s*\.\s*\)|\s+dot\s+|\s*\.\s*)\s*
        {_TLD}\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Phrases that signal overt self-promotion regardless of subreddit policy.
_DEFAULT_SELF_PROMO_PHRASES = [
    "dm me", "check out my", "i built", "i made", "my product", "my startup",
    "my app", "my site", "my website", "my tool", "sign up", "use code",
    "discount code", "affiliate", "my company", "we built", "we launched",
]


@dataclass
class SubredditPolicy:
    """Structured, enforceable policy for one subreddit.

    Built ONCE from fetched rules (see extract_policy). Conservative defaults:
    when rules can't be fetched or parsed, we assume the strictest stance.
    """

    no_links: bool = True            # fail closed: assume links banned
    no_self_promotion: bool = True   # fail closed: assume self-promo banned
    min_karma: int = 0
    min_account_age_days: int = 0
    banned_phrases: list[str] = field(default_factory=list)

    @classmethod
    def strict_default(cls) -> "SubredditPolicy":
        """The fail-closed policy used when rules are unknown."""
        return cls(no_links=True, no_self_promotion=True)


@dataclass
class GateResult:
    """Outcome of the deterministic gate."""

    allowed: bool
    reasons: list[str] = field(default_factory=list)
    # If links were stripped (and the policy allows posting without them),
    # this holds the cleaned text. None means no rewrite happened.
    rewritten_text: str | None = None

    @property
    def blocked(self) -> bool:
        return not self.allowed


def contains_link(text: str) -> bool:
    """True if the text contains a URL or an obfuscated URL."""
    scrubbed = _strip_prose_abbreviations(text)
    return bool(_URL_RE.search(scrubbed) or _OBFUSCATED_RE.search(scrubbed))


def strip_links(text: str) -> str:
    """Remove URLs (including obfuscated) and collapse leftover whitespace.

    Common prose abbreviations (e.g., i.e.) are preserved — only real/obfuscated
    links are removed.
    """
    # Operate on the original text so abbreviations survive, but the link regexes
    # won't match them because they don't have a domain-like left side after a TLD.
    cleaned = _OBFUSCATED_RE.sub("", _URL_RE.sub("", text))
    # Restore any abbreviation that got caught (defensive — they rarely match).
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def deterministic_gate(
    comment_text: str,
    policy: SubredditPolicy,
    account_karma: int,
    account_age_days: int | None,
    strip_links_if_banned: bool = True,
) -> GateResult:
    """Run the deterministic compliance gate. Pure function, no I/O.

    Args:
        comment_text: the generated comment.
        policy: the subreddit's structured policy.
        account_karma: current account karma.
        account_age_days: account age in days, or None if unknown.
        strip_links_if_banned: if True and links are banned, strip them and
            allow (if nothing else blocks); if False, block on any link.

    Returns:
        GateResult. A block here is TERMINAL — do not regenerate.
    """
    reasons: list[str] = []
    text = comment_text or ""
    rewritten: str | None = None

    if not text.strip():
        return GateResult(allowed=False, reasons=["empty comment"])

    # --- Karma (fail closed is implicit: low karma blocks) ---
    if policy.min_karma > 0 and account_karma < policy.min_karma:
        reasons.append(
            f"karma {account_karma} < required {policy.min_karma}"
        )

    # --- Account age (fail closed when unknown but required) ---
    if policy.min_account_age_days > 0:
        if account_age_days is None:
            reasons.append(
                f"account age unknown but sub requires "
                f"{policy.min_account_age_days}d (fail closed)"
            )
        elif account_age_days < policy.min_account_age_days:
            reasons.append(
                f"account age {account_age_days}d < required "
                f"{policy.min_account_age_days}d"
            )

    # --- Banned phrases ---
    lowered = text.lower()
    hit_phrases = [p for p in policy.banned_phrases if p.lower() in lowered]
    if hit_phrases:
        reasons.append(f"banned phrases: {', '.join(hit_phrases)}")

    # --- Self-promotion ---
    if policy.no_self_promotion:
        promo_hits = [p for p in _DEFAULT_SELF_PROMO_PHRASES if p in lowered]
        if promo_hits:
            reasons.append(f"self-promotion signals: {', '.join(promo_hits)}")

    # --- Links ---
    if policy.no_links and contains_link(text):
        if strip_links_if_banned:
            rewritten = strip_links(text)
            if not rewritten:
                # Stripping links left nothing meaningful — block.
                reasons.append("comment was only a link")
            else:
                log.info("Stripped banned link(s) from comment before posting")
        else:
            reasons.append("contains link in a no-links subreddit")

    if reasons:
        log.warning(f"Deterministic gate BLOCKED: {'; '.join(reasons)}")
        return GateResult(allowed=False, reasons=reasons)

    return GateResult(allowed=True, rewritten_text=rewritten)


def extract_policy(report_json: str, subreddit_config) -> SubredditPolicy:
    """Build a SubredditPolicy from a stored intel report + subreddit config.

    The intel report (JSON from subreddit_intel) gives a fuzzy read of the
    rules; we translate it into hard policy, failing closed on anything
    ambiguous. Per-sub overrides from subreddits.yaml (min_karma,
    min_account_age_days) always win.
    """
    import json

    policy = SubredditPolicy.strict_default()

    # Per-sub config overrides (authoritative).
    policy.min_karma = getattr(subreddit_config, "min_karma", 0) or 0
    policy.min_account_age_days = (
        getattr(subreddit_config, "min_account_age_days", 0) or 0
    )

    if not report_json:
        log.info("No intel report; using strict-default policy (fail closed)")
        return policy

    try:
        report = json.loads(report_json)
    except (json.JSONDecodeError, TypeError):
        log.warning("Intel report unparseable; using strict-default policy")
        return policy

    # self_promotion_tolerance: low/medium/high
    tolerance = str(report.get("self_promotion_tolerance", "low")).lower()
    policy.no_self_promotion = tolerance not in ("medium", "high")

    # Infer no_links from the avoid list. Default stays True (fail closed)
    # unless the report clearly signals links are tolerated.
    avoid = [str(a).lower() for a in report.get("avoid", [])]
    avoid_text = " ".join(avoid)
    if "link" in avoid_text or "url" in avoid_text or "self-prom" in avoid_text:
        policy.no_links = True
    elif tolerance == "high":
        # High-tolerance subs typically allow links.
        policy.no_links = False

    # Pull explicit banned phrases the report may surface.
    policy.banned_phrases = [
        str(a) for a in report.get("avoid", []) if len(str(a)) <= 40
    ]

    return policy
