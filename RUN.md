# Running the agent

How to run reddit-agent as a continuous, self-healing loop — and what to do when
something goes wrong. This is the operator's guide; for setup see `INSTALL.md`,
for research mode see `RESEARCH.md`, for deployment see `DEPLOY_RESEARCH.md`.

## The two cadences

The agent does two different things on two different rhythms:

| Activity        | Mode             | Cadence                         | Writes to Reddit? |
|-----------------|------------------|---------------------------------|-------------------|
| Comment/post    | engagement cycle | every `CYCLE_INTERVAL_HOURS` (~2h), capped at `MAX_COMMENTS_PER_DAY` | yes |
| Lead discovery  | research pass    | continuous (read-only)          | no                |

**Posting is deliberately slow and quota-bound** — that's what keeps the account
looking human and avoids filters/bans. **Research is read-only** and can run as
often as you like, *subject to Reddit's rate limits* (see "The 403 block" below).

Set the rhythm in `.env`:

```
CYCLE_INTERVAL_HOURS=2        # min hours between engagement cycles
MAX_COMMENTS_PER_DAY=2        # daily posting quota
RESEARCH_MODE=after_quota     # off | after_quota | only
```

- `after_quota` — post when it's time and quota remains, otherwise do research.
  This is the recommended 24/7 setting: the loop is never idle.
- `only` — pure discovery, never posts (good for warming/observation).
- `off` — engagement only.

## Run it

One tick (post if due, else research). This is what a cron/launchd/systemd timer
or a driving agent calls on a schedule:

```bash
deploy/heartbeat.sh                 # honors the breaker, quota, and research mode
# or directly:
.venv/bin/python -m src.main        # one full cycle
.venv/bin/python -m src.main --research   # one research pass only (read-only)
```

For always-on hosting (laptop closed / a VPS), wire `deploy/heartbeat.sh` into a
timer — see `DEPLOY_RESEARCH.md`. The agent is **not** a long-running daemon; each
tick is a short invocation, so a crash never takes down the loop.

## Check status (no actions taken)

```bash
.venv/bin/python -m src.main --status     # JSON snapshot
.venv/bin/python -m src.main --audit      # self-audit + auto-heal report
```

`--status` reports `should_run`, `paused`, today's `comments` vs `comment_limit`,
`research_mode`, and `opportunities.total`. A driving agent polls this to decide
whether to run.

## Read the output

- `data/opportunities.md` / `.json` / `.csv` — the ranked lead list (research
  mode). Generate the CSV on demand with `reddit-agent --export-csv` (sorted by
  priority: subreddit, title, URL, problem, suggested angle, matched services).
  Falls back to scanned threads if no opportunities are classified yet.
- `data/research_insights.md` — what's getting traction; feeds future passes.
- `data/learnings.md` — auto-captured wins/removals/bans per subreddit.
- `data/screenshots/error_*.png` — **the page state at the moment of a failure.**
  Always read these before guessing at a DOM/selector problem.

## When something breaks

The agent self-heals where it safely can (the watchdog fixes an uninitialized DB,
prunes screenshot/disk overflow). For the rest:

**Paused (circuit breaker tripped).** `--status` shows `"paused": true` with an
alert. The breaker trips on a shadowban, a removal spike, or repeated rule blocks.
Investigate the alert, then clear it:
```bash
.venv/bin/python -m src.main --resume
```

**`comment_box_not_found` on one subreddit.** Usually means the account is
**banned** from that community (Reddit renders no composer for banned users). The
agent detects the ban banner, cools the sub down for a year, and records it to
learnings — so it stops trying. Confirm by reading the latest error screenshot.

**"You've been blocked by network security" (HTTP 403).** Reddit's anti-bot wall.
Two kinds:
- *Search endpoints* (`/search/`) are **always** blocked for automation — the agent
  knows this and discovers via subreddit feeds + LLM suggestions instead.
- *Feeds/threads* get blocked only under **request velocity** — too many requests
  too fast from one IP. The agent backs off and retries; a sustained block makes a
  research pass abort cleanly and resume on the next pass. **The cure is time** —
  stop hitting Reddit for a while (minutes to ~an hour) and it lifts. Don't poll
  feeds aggressively; the built-in cadence is tuned to stay under the limit.

**Expired/missing cookies.** `--audit` flags it. Re-export cookies (see
`INSTALL.md`); a datacenter IP (VPS) needs exported residential-session cookies —
datacenter IPs are blocked outright.

## The golden rule

Respect the cadence. The single most common way to break a healthy account is to
drive it too hard — rapid requests trip the 403 block, and aggressive posting trips
filters/bans. Slow is fast: let the agent pace itself, and it runs indefinitely.
