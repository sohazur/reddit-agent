# Deploy the 24/7 Research agent — where to put your secrets

Nothing sensitive goes in git or in chat. The agent reads **env vars** for
credentials and one **file** (`data/cookies.json`) for the Reddit session. Both
`.env` and `data/cookies.json` are gitignored.

## What the agent needs

| Secret | How it's consumed | Required? |
|---|---|---|
| `REDDIT_USERNAME` | env var | ✅ |
| `REDDIT_PASSWORD` | env var | ✅ |
| `data/cookies.json` | file (Reddit blocks headless login) | ✅ |
| `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) | env var | ✅ for LLM calls |
| `SLACK_WEBHOOK_URL` | env var | optional (alerts/digest) |
| `REACHLLM_OPPORTUNITIES_URL` / `REACHLLM_API_TOKEN` | env var | optional (push) |

Plus the mode switch: `RESEARCH_MODE=after_quota` (or `only`).

## The one trick: cookies are a file, secret stores hold env vars

Export your cookie jar once, base64-encode it, and store the blob as an env var.
A startup script decodes it back to `data/cookies.json`.

**1. Export cookies** (logged in to Reddit as the bot account):
- Chrome/Firefox + the [Cookie-Editor](https://cookie-editor.com) extension → go to reddit.com → **Export as JSON** → save as `cookies.json`.

**2. Base64-encode it** (on your laptop):
```bash
base64 -w0 cookies.json   # Linux
base64 cookies.json        # macOS (no -w0)
```
Copy the output.

**3. Set these env vars / secrets in your environment:**
```
REDDIT_USERNAME=your_bot_username
REDDIT_PASSWORD=your_bot_password
ANTHROPIC_API_KEY=sk-ant-...
RESEARCH_MODE=after_quota
REDDIT_COOKIES_B64=<the base64 blob from step 2>
```

**4. At startup, materialize the file:**
```bash
bash deploy/materialize_secrets.sh   # writes data/cookies.json from REDDIT_COOKIES_B64
```

## Claude Code on the web

- Put `REDDIT_USERNAME`, `REDDIT_PASSWORD`, `ANTHROPIC_API_KEY`, `RESEARCH_MODE`,
  and `REDDIT_COOKIES_B64` in the **environment's env-var/secret config** (see
  https://code.claude.com/docs/en/claude-code-on-the-web).
- Add a **SessionStart hook** (or setup script) that runs
  `bash deploy/materialize_secrets.sh` so the cookie file exists each session.
- Note: web sessions are not a persistent daemon. For true round-the-clock
  operation, run the heartbeat on an always-on host (below).

## Always-on host (cron / systemd)

```bash
# .env on the host (gitignored), or real env vars:
RESEARCH_MODE=after_quota

# materialize cookies once at boot / before each run:
bash deploy/materialize_secrets.sh

# then run the heartbeat on a timer — it self-schedules via --status:
*/30 * * * * cd /path/to/reddit-agent && bash deploy/heartbeat.sh >> data/heartbeat.log 2>&1
```
systemd unit + timer templates are in `deploy/systemd/`.

## Verify it's healthy (no posting)

```bash
reddit-agent audit      # JSON health report; flags missing/expired cookies
reddit-agent --status   # shows research_mode + opportunity counts
reddit-agent research   # one read-only discovery pass
cat data/opportunities.md
```

The watchdog auto-heals safe issues every cycle and alerts you (Slack) on the
ones only you can fix — chiefly a missing or expired cookie jar (re-do the
export + `REDDIT_COOKIES_B64` steps when that happens, roughly every few weeks).
