"""Discover where to look: candidate subreddits and threads for our services.

Three independent sources, each best-effort:
  1. LLM brainstorm  — suggest subreddits from the service catalog + objective.
  2. Reddit search   — sitewide search for service "signal" phrases (browser).
  3. Web search      — optional, via the Anthropic web-search tool.

Pure helpers (URL/query building, suggestion parsing) are split out so they can
be tested without a browser or network.
"""

import json
import re
from urllib.parse import quote_plus

from src.config import Config, ServiceCatalog, load_prompt
from src.llm import call_llm, get_provider
from src.log import get_logger
from src.research.services import format_services_block
from src.research import store

log = get_logger("research.discovery")

_SUB_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")


# ─── Pure helpers ──────────────────────────────────────────────────────────


def normalize_sub_name(raw: str) -> str | None:
    """Clean a model-supplied subreddit name; return None if implausible."""
    if not raw:
        return None
    name = raw.strip().lstrip("/").removeprefix("r/").removeprefix("R/").strip().rstrip("/")
    name = name.split("/")[0]
    return name if _SUB_RE.match(name) else None


def parse_subreddit_suggestions(text: str) -> list[dict]:
    """Parse the LLM's JSON array of {name, relevance, rationale}."""
    if not text:
        return []
    raw = text.strip()
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        log.warning("Could not parse subreddit suggestions")
        return []
    if not isinstance(data, list):
        return []

    out = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = normalize_sub_name(item.get("name", ""))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        try:
            relevance = max(0, min(10, int(item.get("relevance", 0))))
        except (TypeError, ValueError):
            relevance = 0
        out.append({
            "name": name,
            "relevance": relevance,
            "rationale": str(item.get("rationale", "")).strip()[:240],
        })
    return out


def build_search_queries(catalog: ServiceCatalog, limit: int = 6) -> list[str]:
    """Distinct sitewide-search phrases from service signals (most specific first)."""
    queries: list[str] = []
    seen = set()
    for svc in catalog.services:
        for sig in svc.signals:
            q = sig.strip().strip('"').lower()
            # Skip overly short/generic single words that would flood results.
            if len(q) < 6 or q in seen:
                continue
            seen.add(q)
            queries.append(sig.strip().strip('"'))
            if len(queries) >= limit:
                return queries
    return queries


def reddit_search_url(query: str, sort: str = "new", time: str = "month") -> str:
    """Build a Reddit sitewide search URL for a phrase."""
    return (
        f"https://www.reddit.com/search/?q={quote_plus(query)}"
        f"&sort={sort}&t={time}"
    )


def subreddit_from_url(url: str) -> str:
    """Extract the subreddit name from a Reddit thread URL ('' if not found)."""
    m = re.search(r"/r/([A-Za-z0-9_]+)/", url or "")
    return m.group(1) if m else ""


# ─── LLM brainstorm ────────────────────────────────────────────────────────


def suggest_subreddits_via_llm(config: Config, catalog: ServiceCatalog) -> list[dict]:
    """Ask the LLM for subreddits to track; persist them as candidates."""
    known = [s["name"] for s in store.get_research_subreddits(exclude_status="zzz")]
    known += [s.name for s in config.subreddits]
    prompt = load_prompt(
        "suggest_subreddits",
        company_name=catalog.company_name or "our company",
        company_one_liner=catalog.company_one_liner or "",
        services_block=format_services_block(catalog),
        audiences=", ".join(catalog.audiences) or "our target customers",
        objective=config.objective or "find people we can help",
        known_subreddits=", ".join(sorted(set(known))) or "(none yet)",
    )
    try:
        text = call_llm(prompt, max_tokens=600)
    except Exception as e:
        log.error(f"Subreddit suggestion LLM error: {e}")
        return []

    suggestions = parse_subreddit_suggestions(text)
    for s in suggestions:
        store.upsert_research_subreddit(
            s["name"], discovered_via="llm",
            relevance=s["relevance"], rationale=s["rationale"],
        )
    log.info(f"LLM suggested {len(suggestions)} subreddits")
    return suggestions


# ─── Web search (optional, Anthropic) ──────────────────────────────────────


def discover_subreddits_via_web(config: Config, catalog: ServiceCatalog) -> list[dict]:
    """Use the Anthropic web-search tool to find communities, if enabled.

    Best-effort and fully guarded: any failure (no key, wrong provider, SDK
    shape change) returns [] without disrupting the cycle.
    """
    if not config.research_web_search:
        return []
    if get_provider() != "anthropic":
        log.info("Web-search discovery skipped (needs Anthropic provider)")
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        query = (
            f"Find active Reddit communities (subreddits) where people discuss or "
            f"ask for help with: {catalog.company_one_liner or config.objective}. "
            f"Return a JSON array of objects with keys name, relevance (1-10), "
            f"rationale. Subreddit names only, no 'r/'."
        )
        resp = client.messages.create(
            model=config.__dict__.get("research_model") or "claude-sonnet-4-20250514",
            max_tokens=800,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": query}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", "") == "text"
        )
    except Exception as e:
        log.warning(f"Web-search discovery failed (ignored): {e}")
        return []

    suggestions = parse_subreddit_suggestions(text)
    for s in suggestions:
        store.upsert_research_subreddit(
            s["name"], discovered_via="web_search",
            relevance=s["relevance"], rationale=s["rationale"],
        )
    log.info(f"Web search suggested {len(suggestions)} subreddits")
    return suggestions


# ─── Reddit sitewide search (browser) ──────────────────────────────────────


async def discover_threads_via_search(
    session, config: Config, catalog: ServiceCatalog, per_query: int = 10
) -> list[dict]:
    """Run Reddit sitewide searches for service signals; return candidate threads.

    Each thread dict: {id, title, url, score, comment_count, subreddit}.
    Subreddits seen here are also registered as discovered candidates.
    """
    from src.browser.actions import SearchBlockedError, extract_search_results
    from src.browser.stealth import human_delay
    import asyncio

    threads: list[dict] = []
    seen_urls = set()
    for query in build_search_queries(catalog):
        url = reddit_search_url(query)
        try:
            results = await extract_search_results(session, url, limit=per_query)
        except SearchBlockedError as e:
            # Reddit blocks all search endpoints for automation. Stop the whole
            # loop on the first block — retrying every query only deepens the
            # rate-block and never succeeds. Feed scanning carries discovery.
            log.warning(f"{e} — skipping search discovery this pass")
            break
        except Exception as e:
            log.warning(f"Search failed for '{query}': {e}")
            continue
        for r in results:
            u = r.get("url", "")
            if not u or u in seen_urls:
                continue
            seen_urls.add(u)
            sub = subreddit_from_url(u)
            r["subreddit"] = sub
            threads.append(r)
            if sub and not store.subreddit_known(sub):
                store.upsert_research_subreddit(sub, discovered_via="reddit_search")
        await asyncio.sleep(human_delay(2000, 5000))

    log.info(f"Reddit search surfaced {len(threads)} candidate threads")
    return threads
