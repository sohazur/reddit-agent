# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.12.2] - 2026-06-04

### Changed
- **Default OpenRouter model is now `minimax/minimax-m3`** (a reasoning model) instead of the free Gemma. Reasoning is enabled by default; since reasoning tokens count against `max_tokens`, OpenRouter calls now floor the budget at 2048 so the actual answer isn't truncated. Disable reasoning with `REDDIT_AGENT_REASONING=false`. As always, swap models via `REDDIT_AGENT_MODEL` with no code change. Verified live (the strawberry test returns "3").

## [0.12.1] - 2026-06-04

### Added
- **CSV export of opportunities (where to post).** `reddit-agent --export-csv` writes `data/opportunities.csv` — a spreadsheet of threads to engage, sorted by priority, with subreddit, title, clickable URL, problem summary, suggested angle, matched services, confidence, and status. Every research pass now also writes the CSV alongside the md/json. When no classified opportunities exist yet (e.g. before the first full research pass, or while Reddit is blocked), the export falls back to the raw scanned-thread table so the CSV still lists real Reddit threads. No network needed — pure store read.

## [0.12.0] - 2026-06-04

### Added
- **OpenRouter provider — one key, any model.** Set `OPENROUTER_API_KEY` and the agent routes all LLM calls through OpenRouter (OpenAI-API-compatible), so you can run free or paid models and swap between them with `REDDIT_AGENT_MODEL` — no code change, no per-provider key. OpenRouter takes precedence over Anthropic/OpenAI when its key is present; the default model is a free Gemma (`google/gemma-4-26b-a4b-it:free`). Free models get rate-limited upstream, so OpenRouter calls retry on 429 with backoff (3s, 6s) to stay usable in an unattended loop. Verified live end to end.

## [0.11.4] - 2026-06-04

### Added
- **Adaptive backoff after a network block.** Reddit escalates a repeat-offender IP from a minutes-long velocity block to a multi-hour one, so retrying soon only deepens it. When a research pass is cut short by the block, the agent now records an escalating cool-down (5min → 20min → 60min for consecutive blocks) in `data/block_backoff.json`; `_run_research_safely` skips research while it's active, `--status` surfaces `research_backoff_s`, and a clean pass resets it. The deployed agent now self-paces under blocks instead of hammering Reddit — no operator intervention needed.

## [0.11.3] - 2026-06-04

### Added
- **Network-block recovery with backoff.** Reddit serves a transient "blocked by network security" 403 when requests arrive too fast (a velocity/rate block, distinct from the permanent search-endpoint block). A new `RedditSession.navigate()` routes all reads (feeds, threads, search) through one place that detects the block, backs off with exponential jitter (~8s, ~20s), and retries before raising `NetworkBlockedError`. Feed scanning, thread reading, and search all use it.
- **Fast-abort on a global block.** A network block is IP/session-wide, so once one feed is blocked, every other will be too. Instead of grinding through every subreddit with ~30s of guaranteed-fail backoff each, the research pass now aborts on the first sustained block, reports `network_blocked: true`, keeps whatever it already classified, and lets the next scheduled pass retry after the IP cools down. Posting and feed reads outside research get the same retry resilience.

## [0.11.2] - 2026-06-04

### Fixed
- **Research discovery degrades gracefully when Reddit blocks search.** Reddit hard-blocks automated access to *every* search endpoint — `www`/`old`/`.json`/in-subreddit — with a 403 "You've been blocked by network security" wall (confirmed live). The research pass used Reddit search to find candidate threads, so it silently returned zero opportunities while retrying every blocked query (which only deepens the rate-block). `extract_search_results` now detects the 403/block banner and raises `SearchBlockedError`; discovery stops after the first block and falls back to feed scanning + LLM-suggested subreddits (the paths that aren't blocked). Feeds and threads are unaffected — posting and feed-based discovery keep working.

## [0.11.1] - 2026-06-04

### Fixed
- **Subreddit-ban detection — the real cause of the ~90% "comment_box_not_found" rate.** Live screenshots showed the account is *banned* from r/AskReddit ("You're currently banned from this community and can't comment on posts."). Reddit renders no composer for banned users, so the ban was masquerading as a flaky composer — and the v0.10.1/v0.10.2 scroll "fixes" could never have helped. The agent now detects the ban banner before attempting the composer, returns a distinct `subreddit_banned` error, cools the whole subreddit down for 365 days, and records the reason to learnings — so it stops burning a cycle's attempts on a sub it can't post in. r/AskReddit is now cooled down; posting in r/NoStupidQuestions is unaffected and continues to work.

## [0.11.0] - 2026-06-04

### Added
- **Research / Opportunity-Discovery mode.** A 24/7 lead finder. With
  `RESEARCH_MODE=after_quota|only`, the agent scans Reddit (read-only) for posts
  describing problems your services solve, classifies each against an editable
  catalog (`data/services.yaml`), and builds a ranked list of opportunities
  (links + how-we-help) in `data/opportunities.md`/`.json`. It discovers new
  subreddits (LLM brainstorm, Reddit sitewide search, optional Anthropic web
  search), learns what's getting traction, and can push new opportunities to a
  platform endpoint (`REACHLLM_OPPORTUNITIES_URL`). Because it never posts, it
  keeps running even while the posting circuit breaker is tripped — so the loop
  is never idle. On-demand: `reddit-agent research`. See RESEARCH.md.
- **Self-audit + auto-heal watchdog.** Every cycle (and `reddit-agent audit`)
  the agent checks itself, auto-fixes safe issues (uninitialized DB,
  screenshot/disk overflow), and escalates the rest (missing/expired cookies, a
  tripped breaker) as a single alert — so an unattended agent recovers on its
  own and only pings you when it truly needs you.

### Changed
- `--status` now reports `research_mode` + opportunity counts and keeps
  `should_run` true while paused/quota-spent when research is on. The heartbeat
  no longer hard-stops on a pause when research (read-only) can still run.

## [0.10.2] - 2026-06-02

### Fixed
- Comment posting reliability. The composer was found only ~1 in 9 times because the agent scrolled down into the comment list, past the composer that sits at the top of the comments. It now scrolls the composer into view before looking, and retries the same way. Verified live — a single-thread post test succeeded on the first try.

## [0.10.1] - 2026-06-02

### Fixed
- Shadowban detector no longer false-flags visible comments. It was scrolling too little on large threads, matching text too literally (curly quotes/emoji broke the match), and calling any miss a shadowban — which flagged every comment and paused the agent. It now normalizes text, matches a distinctive word slice, scrolls until found, and assumes visible when unsure. The circuit breaker now requires 2+ invisible comments before pausing, so one flaky check can't stop everything.

## [0.10.0] - 2026-06-02

### Added
- **Account warming phases.** The agent now gates its own behavior by karma so a new account builds trust before promoting: Phase 1 (<50 karma) comments only, no posts, no promotion; Phase 2 (50-199) soft posts; Phase 3 (200+) full strategy. This prevents the exact failure where a low-karma account's promotional post gets filtered by Reddit.
- **Join target subreddits.** The agent subscribes to the subs it's active in (real members behave more naturally and some subs gate posting on membership).
- **Removal cooldowns + reason learning.** When a post or comment is removed (by a mod or Reddit's spam filter), the agent backs off that subreddit for a few days, captures the actual removal reason from the mod/Reddit DM, and records it so future content avoids the same rule.
- **Use the host agent's LLM (no API key needed).** When run inside Cursor/OpenClaw with `LLM_MODE=agent-provided` (or no key set), the agent hands each LLM call to the host's model via a file exchange — so it uses whatever model the host has, with no key of its own. If a real API key is present, it's used directly.

### Changed
- Upvoting now skips the account's own posts and comments (upvoting yourself is a ban signal).

### Fixed
- The agent-provided LLM handoff correlates each response to its request by id, so a late answer to a previous call can never be used for a new one. Cooldown and handoff files are written atomically.

## [0.9.2] - 2026-06-02

### Fixed
- Open the modern Reddit comment composer before posting. The first live run generated good comments but failed to post some of them with "comment_box_not_found" — the editor only appears after clicking an "Add a comment" trigger, and the old selectors were stale. The agent now clicks the trigger (with a legacy fallback), retries once, and submits via Cmd/Ctrl+Enter with a button-click fallback. (First real comment posted successfully during this run.)

## [0.9.1] - 2026-06-02

### Fixed
- Read karma and account age from the current Reddit profile layout. Accounts were being read as 0 karma / unknown age (so karma- and age-gated subreddits were wrongly skipped); the agent now uses the configured username for the profile lookup and parses the modern "5 / Karma" and "3 m / Reddit Age" layout.
- The circuit breaker no longer pauses everything when a strict subreddit's fuzzy judge rejects many comments on fit (e.g. r/explainlikeimfive). Only hard-rule blocks (links, karma, age, banned phrases) count toward the auto-pause; shadowban and removal-rate triggers are unchanged.
- A banned link that can't be cleanly stripped now blocks the comment (so a fresh one is generated) instead of posting a grammatically broken fragment.

## [0.9.0] - 2026-06-02

### Added
- **Compliance gate** — the agent now enforces subreddit rules before posting, not just reads them. A deterministic floor checks links (including obfuscated `dot`/`[.]` forms and any TLD), account karma, account age, banned phrases, and self-promotion; an LLM judge handles fuzzy rules ("stay on topic", "be respectful"). Every uncertain decision fails closed, so a comment that might break a rule never posts.
- **Learns from what works** — your best-performing comments that actually survived feedback get injected as examples into future generation, so the agent replicates your proven voice instead of guessing.
- **Three-tier content mix** — the account now reads as an expert who occasionally has a product, not a shill. It posts mostly pure-value topic content (~70%), sometimes soft-relevance (~25%), and rarely a direct mention (~5%), enforced over a rolling window so promo stays genuinely rare.
- **Runs itself via any agent** — `reddit-agent --status` reports a JSON snapshot (last run, should-run, today's counts vs limits, health, alerts) and `AGENT_LOOP.md` is a single file you hand to any agent (Claude, OpenClaw) to drive the agent on a schedule.
- **Dry-run mode** — `DRY_RUN=true` shows exactly what the agent would post, upvote, or DM without doing any of it, so you can safely onboard a new account or objective.
- **Kill switch** — a global circuit breaker pauses all activity on a shadowban, a removal spike, or repeated rule violations, and stays paused until you run `reddit-agent --resume`.
- **Consistent persona** — an optional per-account identity (voice, interests, backstory) keeps the account reading as one coherent person across months.
- **Account-age awareness** — the agent reads its own cake-day and skips subreddits that require an older account.
- **Production deployment** — `deploy/` ships a heartbeat script, systemd timer/service, a launchd plist, and `DEPLOY.md`, an end-to-end runbook for running the agent on an always-on box.

### Changed
- The `keywords` and `domain` fields now actually drive thread evaluation and content tiering (previously unused).
- New config: `REDDIT_AGENT_DOMAIN`, `TIER_WINDOW`, `DRY_RUN`, and per-subreddit `min_account_age_days`.

### Fixed
- Closed a fail-open in the link gate where links on uncommon TLDs could slip through a no-links subreddit.
- Tier-3 promotional content could briefly exceed its target share on small histories; it now waits until enough value history exists.
