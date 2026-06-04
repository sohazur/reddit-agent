"""Orchestrate one research pass (read-only on Reddit).

Flow:
  1. (periodically) refresh the discovered-subreddit shortlist.
  2. Gather candidate threads: Reddit sitewide search on service signals +
     the feeds of the most relevant discovered/configured subreddits.
  3. Classify each candidate against the service catalog; record real
     opportunities; note high-traction posts for learning.
  4. Write outputs (md/json), push new ones to the platform, refresh insights.

This never comments, upvotes, or DMs — so it is safe to run 24/7, even while
the posting circuit breaker is tripped.
"""

import asyncio
from datetime import datetime, timedelta

from src.browser.session import NetworkBlockedError
from src.config import Config, SubredditConfig, load_service_catalog
from src.log import get_logger
from src.research import store
from src.research.classifier import classify_opportunity
from src.research.discovery import (
    discover_subreddits_via_web,
    discover_threads_via_search,
    suggest_subreddits_via_llm,
)
from src.research.insights import update_research_insights
from src.research.report import write_outputs

log = get_logger("research.runner")


def _discovery_due(config: Config) -> bool:
    """True if the discovered-subreddit shortlist is stale (or empty)."""
    last = store.last_discovery_at()
    if last is None:
        return True
    return datetime.utcnow() - last > timedelta(
        hours=config.research_discovery_interval_hours
    )


async def _candidate_threads(session, config, catalog) -> list[dict]:
    """Collect candidate threads from search + discovered/configured sub feeds."""
    from src.scanner.subreddit import scan_subreddit

    candidates: list[dict] = []
    seen = set()

    def _add(t: dict):
        u = t.get("url", "")
        if u and u not in seen:
            seen.add(u)
            candidates.append(t)

    # 1) Reddit sitewide search on service signals.
    try:
        for t in await discover_threads_via_search(session, config, catalog):
            _add(t)
    except Exception as e:
        log.warning(f"Search discovery failed: {e}")

    # 2) Feeds of the most relevant subreddits (discovered + configured).
    sub_names: list[str] = [
        s["name"] for s in store.get_research_subreddits(limit=config.research_max_subreddits)
    ]
    for s in config.subreddits:
        if s.name not in sub_names:
            sub_names.append(s.name)
    sub_names = sub_names[: config.research_max_subreddits]

    for name in sub_names:
        try:
            sub_cfg = SubredditConfig(name=name, keywords=[], max_daily_comments=0, tone="")
            threads = await scan_subreddit(
                session, sub_cfg, limit=config.research_max_threads_per_sub
            )
            for th in threads:
                _add({
                    "id": th.id, "title": th.title, "url": th.url,
                    "score": th.score, "comment_count": th.comment_count,
                    "subreddit": name,
                })
            store.mark_subreddit_scanned(name)
        except NetworkBlockedError:
            # The IP/session is blocked globally — every remaining sub would
            # fail the same way. Abort the whole pass NOW (don't burn ~30s of
            # backoff per remaining sub) and let run_research_pass schedule a
            # longer cool-down before the next attempt.
            raise
        except Exception as e:
            log.warning(f"Feed scan failed for r/{name}: {e}")
        await asyncio.sleep(2)

    return candidates


async def run_research_pass(config: Config, session) -> dict:
    """Run one research pass and return a summary dict."""
    catalog = load_service_catalog()
    results = {
        "candidates": 0,
        "classified": 0,
        "opportunities_new": 0,
        "viral_seen": 0,
        "pushed": 0,
    }

    if not catalog.services:
        log.warning("No services configured (data/services.yaml) — research idle")
        return results

    log.info("Research pass starting")

    # 1) Refresh discovery when stale.
    if _discovery_due(config):
        try:
            suggest_subreddits_via_llm(config, catalog)
            discover_subreddits_via_web(config, catalog)
        except Exception as e:
            log.warning(f"Discovery refresh failed: {e}")

    # 2) Candidate threads. A persistent network block (rate-limit that didn't
    # clear within navigate()'s backoff) ends the pass cleanly — the next
    # scheduled pass retries once Reddit has cooled off.
    from src.safety import block_backoff

    results["network_blocked"] = False
    try:
        candidates = await _candidate_threads(session, config, catalog)
    except NetworkBlockedError as e:
        log.warning(f"Research pass cut short by network block: {e}")
        candidates = []
        results["network_blocked"] = True
        # Escalating cool-down so the driver holds off (and doesn't deepen the
        # block) before the next pass. Cleared below on a successful pass.
        results["backoff_s"] = block_backoff.record_block()
    else:
        # We reached Reddit without a sustained block — reset any backoff.
        block_backoff.clear()
    results["candidates"] = len(candidates)

    # 3) Classify each candidate.
    from src.scanner.subreddit import read_thread_details

    for cand in candidates:
        url = cand.get("url", "")
        if not url:
            continue
        opp_id = store.opportunity_id(url)
        if store.opportunity_exists(opp_id):
            continue  # already a known opportunity

        # Record high-traction posts for the learning layer regardless of fit.
        if cand.get("score", 0) >= 100:
            store.record_viral_observation(
                cand.get("id", ""), cand.get("subreddit", ""),
                cand.get("title", ""), url, cand.get("score", 0),
                cand.get("comment_count", 0),
            )
            results["viral_seen"] += 1

        try:
            details = await read_thread_details(session, url)
        except NetworkBlockedError as e:
            # A sustained block won't clear mid-pass — stop reading threads now
            # rather than backing off on every remaining candidate. Whatever was
            # classified so far is kept; the next pass resumes.
            log.warning(f"Network block during classification, ending pass early: {e}")
            results["network_blocked"] = True
            break
        except Exception as e:
            log.warning(f"Could not read {url}: {e}")
            continue

        comments_text = "\n".join(
            f"u/{c.get('author', 'anon')}: {c.get('body', '')}"
            for c in details.get("comments", [])[:8]
        )
        body = details.get("body", "") or cand.get("title", "")

        opp = await classify_opportunity(
            config, catalog,
            subreddit=cand.get("subreddit", "") or "unknown",
            thread_title=cand.get("title", "") or details.get("title", ""),
            thread_body=body,
            thread_comments=comments_text,
        )
        results["classified"] += 1

        if opp.is_opportunity and opp.priority >= config.research_min_priority:
            store.record_opportunity(
                url=url,
                subreddit=cand.get("subreddit", ""),
                thread_id=cand.get("id", ""),
                title=cand.get("title", "") or details.get("title", ""),
                author=details.get("author", "") or cand.get("author", ""),
                problem_summary=opp.problem_summary,
                matched_services=opp.matched_services,
                suggested_angle=opp.suggested_angle,
                priority=opp.priority,
                confidence=opp.confidence,
            )
            results["opportunities_new"] += 1
            log.info(
                f"Opportunity (p{opp.priority}) r/{cand.get('subreddit')}: "
                f"{opp.problem_summary[:80]}"
            )

        await asyncio.sleep(1)

    # 4) Outputs + push + insights.
    try:
        write_outputs(catalog)
        from src.integrations.reachllm import push_new_opportunities
        push_res = push_new_opportunities(config)
        results["pushed"] = push_res.get("pushed", 0)
        update_research_insights()
    except Exception as e:
        log.error(f"Research output stage failed: {e}")

    log.info(
        f"Research pass complete: {results['opportunities_new']} new opportunities "
        f"from {results['classified']} classified ({results['candidates']} candidates)"
    )
    return results
