# Research / Opportunity-Discovery Mode

Turn the agent into a 24/7 lead finder. Instead of (or in addition to) posting,
it continuously scans Reddit for posts that describe problems **your services
solve**, ranks them, and builds a list you can act on — links + a short "how
we'd help" for each. It also learns what's getting traction in your niche.

**Research is read-only on Reddit.** It never comments, upvotes, or DMs — so it
is safe to run around the clock, even while the posting circuit breaker is
tripped.

## Quick start

1. Describe what you sell in `data/services.yaml` (it ships seeded with a
   ReachLLM example — visibility tracking, technical SEO, GEO/AEO, content,
   Reddit, PR, guaranteed engagement). Each service lists the problems it
   `solves`, the `signals` that hint at a fit, and a one-line `pitch`.

2. Turn on the mode in `.env`:

   ```bash
   RESEARCH_MODE=after_quota   # off | after_quota | only
   ```

3. Run it:

   ```bash
   reddit-agent research   # one pass on demand
   # …or just let the normal loop run — research kicks in automatically
   ```

## Modes

| `RESEARCH_MODE` | Behavior |
|---|---|
| `off` | Disabled (default). Original engagement-only behavior. |
| `after_quota` | Engage normally, then research the rest of the time — including cycles where the daily comment quota is already spent or posting is paused. The agent never idles. |
| `only` | Pure passive discovery. Never comments/upvotes/DMs. Lowest ban risk. |

## What a pass does

```
1. Refresh discovery (when stale)   → brainstorm + web-search new subreddits
2. Gather candidate threads         → Reddit sitewide search on service signals
                                       + feeds of the most relevant subreddits
3. Classify each thread             → LLM maps it to your services, scores
                                       priority 1-10, writes a problem summary
4. Record opportunities >= priority → deduped by URL, with the matched services
5. Write outputs + push + learn     → see below
```

## Outputs

| File | What |
|---|---|
| `data/opportunities.md` | Ranked, human-readable lead list (links + how-we-help). |
| `data/opportunities.json` | Machine-readable, same data. |
| `data/research_insights.md` | Where opportunities cluster + what's getting traction. |

These live in `data/` (gitignored) and persist across updates.

### Push to your platform (optional)

Set an endpoint and the agent POSTs **new** opportunities to it (with an
optional bearer token), then marks them `pushed` so they aren't sent twice:

```bash
REACHLLM_OPPORTUNITIES_URL=https://app.reachllm.com/api/reddit-opportunities
REACHLLM_API_TOKEN=...
```

Payload shape: `{ company, generated_at, count, opportunities: [ { url, title,
subreddit, priority, confidence, problem_summary, matched_services,
suggested_angle, ... } ] }`. If no URL is set, this is a silent no-op.

## Tuning

| Env | Default | What |
|---|---|---|
| `RESEARCH_MIN_PRIORITY` | 6 | Only record opportunities scoring at least this (1-10). |
| `RESEARCH_MAX_SUBREDDITS` | 8 | Subreddit feeds inspected per pass. |
| `RESEARCH_MAX_THREADS_PER_SUB` | 12 | Threads pulled per subreddit feed. |
| `RESEARCH_DISCOVERY_INTERVAL_HOURS` | 24 | How often to refresh the discovered-subreddit shortlist. |
| `RESEARCH_WEB_SEARCH` | false | Use the Anthropic web-search tool to find new communities (needs `ANTHROPIC_API_KEY`). |

## Self-audit & auto-heal

For unattended runs, the agent audits itself at the start of every cycle and on
demand:

```bash
reddit-agent audit   # JSON health report, no actions
```

It auto-fixes the safe failure modes (uninitialized DB, error-screenshot/disk
overflow) and escalates the rest (missing/expired cookies, a tripped breaker)
as a single Slack alert — so it recovers on its own and only pings you when it
genuinely needs you.
