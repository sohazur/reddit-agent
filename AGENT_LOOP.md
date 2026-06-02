# Agent Loop — hand this to any agent (Claude, OpenClaw, Codex, …)

This is the whole job. You (the agent) are the **scheduler**. The `reddit-agent`
tool reports its own state and does the work; you decide *when* to run it and
*when to stop and ask the human*.

## The loop

Run this every time you wake up (a heartbeat, a cron tick, or when the human asks
"how's Reddit going?"):

```
1. status = run: reddit-agent --status        # JSON, takes no action
2. if status.alerts is non-empty:
     - tell the human each alert
     - if status.paused: STOP. Do not run. Wait for the human to investigate.
       (They clear it with: reddit-agent --resume)
3. if status.should_run:
     - run: reddit-agent                       # one engagement cycle
     - report what happened (posted / skipped / blocked)
4. once per day, on your first wake-up:
     - run: reddit-agent --digest              # daily summary for the human
5. otherwise: do nothing, check again next heartbeat
```

That's it. Don't build your own timers or quotas — `--status` already tells you
`should_run`, factoring in the cycle interval, the daily quota, and the pause
state.

## Reading `reddit-agent --status`

```json
{
  "last_run": "2026-06-02T08:00:00+00:00",
  "hours_since": 4.2,
  "cycle_interval_hours": 2,
  "should_run": true,
  "paused": false,
  "paused_reason": null,
  "dry_run": false,
  "today": { "comments": 2, "comment_limit": 5, "quota_left": 3 },
  "alerts": []
}
```

- `should_run` — run a cycle if true. If false, do nothing this tick.
- `paused` — the circuit breaker tripped (shadowban, removals, or too many
  rule violations). **Never run while paused.** Surface `paused_reason` to the
  human; only they decide to `--resume`.
- `dry_run` — if true, cycles generate and log what they *would* do but post
  nothing. Use this to onboard a new account or a new objective safely.
- `alerts` — always relay these to the human verbatim.

## Onboarding a new account (do this first)

1. Set `DRY_RUN=true` in `.env`.
2. Run `reddit-agent` a few times. Read the `[DRY RUN] WOULD POST` lines.
3. If the voice and targeting look right, set `DRY_RUN=false` and resume the loop.

## Commands you have

| Command | What it does | Mutates? |
|---|---|---|
| `reddit-agent --status` | JSON snapshot for this loop | no |
| `reddit-agent` | run one engagement cycle | yes (unless DRY_RUN) |
| `reddit-agent --feedback` | check past comments only | no posting |
| `reddit-agent --digest` | daily summary for the human | no |
| `reddit-agent --resume` | clear the circuit breaker | resumes posting |

## The rules the tool enforces for you (so you don't have to)

You don't police any of this — the tool does, and refuses to act when it would
break a rule:

- **Compliance gate** — checks each comment against subreddit rules before
  posting (links, karma, account age, banned phrases, self-promotion) plus an
  LLM judge for fuzzy rules. Fails closed.
- **Rate limits** — daily quota + per-sub quota + jittered cooldown between posts.
- **Karma/age gating** — skips subs the account doesn't qualify for.
- **Circuit breaker** — pauses everything on a shadowban or a removal/violation
  spike, and tells you via `--status`.
- **Three-tier mix** — keeps the account mostly helpful (≈70%), occasionally
  relevant (≈25%), rarely promotional (≈5%).

Your job is the schedule and the human relationship. The tool's job is to act
safely. Keep them separate.
