# Install Reddit Agent

You are an AI agent helping a user set up autonomous Reddit engagement.

## Step 1: Install

```bash
npm i -g reddit-agent
```

## Step 2: Run interactive setup

**DO NOT ask the user for their Reddit password in chat.** Instead, run the setup command which handles credentials locally on the machine:

```bash
reddit-agent setup
```

This command runs interactively and prompts the user directly for:
- Reddit username
- Reddit password (typed locally, never sent through chat)
- Their objective/goal
- How many comments per day

Tell the user:
> "I've started the setup. It's asking for your Reddit credentials directly on the machine — your password stays local and won't appear in our chat. Please enter your details when prompted."

**If the user is remote (chatting via WhatsApp/Telegram and can't see the terminal):**

Option A — Have them SSH in and run it:
> "For security, your Reddit password shouldn't go through chat. Run this on your server:
> `ssh root@YOUR_SERVER` then `reddit-agent setup`"

Option B — Have them set ONLY the password via a secure method:
```bash
# You (the agent) set everything except the password:
INSTALL_DIR=$(npm root -g)/reddit-agent

cat > "$INSTALL_DIR/.env" << EOF
REDDIT_USERNAME=<ask the user for their username — this is public, OK to share>
REDDIT_PASSWORD=CHANGE_ME
REDDIT_AGENT_OBJECTIVE=<their objective>
MAX_COMMENTS_PER_DAY=5
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
CYCLE_INTERVAL_HOURS=2
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
```

Then tell the user:
> "I've configured everything except your Reddit password. Please run this one command to set it securely:
> `reddit-agent setup-password`
> Or manually edit the .env file and replace CHANGE_ME with your password."

Option C — If the user insists on sharing the password in chat:
Accept it, configure the system, and remind them to change their Reddit password afterward since it was shared in plaintext.

## Step 3: Ask the user these questions (safe to ask in chat)

1. **Reddit username** — "What's your Reddit username?" (this is public info)
2. **Objective** — "What's your goal on Reddit? Examples:
   - Promote my SaaS product to developers
   - Build authority in the fitness niche  
   - Drive traffic to my blog about AI
   - Get visibility for my consulting business
   - Just build karma on a new account"
3. **Target subreddits** (optional) — "Any specific subreddits? Or should I find the best ones?"
4. **How many comments per day?** — default 5

## Step 4: Configure subreddits based on their objective

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`.

Based on the user's objective, create a subreddit list:
- 2-3 **karma building** subreddits (min_karma: 0) like AskReddit, NoStupidQuestions
- 2-4 **target** subreddits relevant to their objective (min_karma: 20-50)

Each subreddit needs:
```yaml
- name: SubredditName
  keywords: [relevant, topics, for, their, goal]
  max_daily_comments: 2
  min_karma: 0          # 0 for karma building, 20-50 for target subs
  tone: "Match community style"
  notes: "Any rules to follow"
```

## Step 5: Cookie setup (if on a VM/cloud server)

Reddit blocks datacenter IPs. Ask the user:

> "Reddit blocks cloud server IPs. I need your browser cookies to bypass this.
> Please:
> 1. Log in to Reddit on your phone/laptop
> 2. Install the Cookie-Editor browser extension
> 3. Export cookies for reddit.com as JSON
> 4. Send me the JSON here"

Save cookies to: `$(npm root -g)/reddit-agent/data/cookies.json`

Skip this step if the user is on a personal computer.

## Step 6: First run

```bash
reddit-agent run
```

Report results to the user.

## Step 7: Confirm it's working

Tell the user:
> "Reddit agent is set up! It will:
> - Post [X] comments per day across [Y] subreddits
> - Build karma automatically
> - Learn from feedback and improve
> - Check inbox for bans/removals before every cycle
> - You can ask me: 'How's Reddit doing?' or 'Run the Reddit bot'"

## Ongoing commands

| User says | Do this |
|---|---|
| "Run the Reddit bot" | `reddit-agent run` then report |
| "How's Reddit doing?" | `reddit-agent digest` |
| "Add r/whatever" | Edit subreddits.yaml |
| "Change my objective" | `reddit-agent objective "new goal"` |
| "Post more/less" | Edit MAX_COMMENTS_PER_DAY in .env |
| "Stop posting" | Set MAX_COMMENTS_PER_DAY=0 in .env |
| "What did it learn?" | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| "Update the agent" | `reddit-agent update` |
