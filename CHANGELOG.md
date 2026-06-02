# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
