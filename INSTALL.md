# Install Reddit Agent

You are an AI agent helping a user set up autonomous Reddit engagement.

## Step 1: Install

```bash
npm i -g reddit-agent
```

## Step 2: Ask the user these questions

1. **Reddit username** — "What's the Reddit username you want to use?"
2. **Reddit password** — "What's the password for that account?"
3. **Objective** — "What's your goal on Reddit? For example:
   - Promote my SaaS product to developers
   - Build authority in the fitness niche
   - Drive traffic to my blog about AI
   - Get visibility for my consulting business
   - Just build karma on a new account"
4. **Target subreddits** (optional) — "Any specific subreddits you want to post in? Or should I find the best ones for your goal?"
5. **How many comments per day?** — default is 5

## Step 3: Configure

Write the credentials:
```bash
INSTALL_DIR=$(npm root -g)/reddit-agent
cat > "$INSTALL_DIR/.env" << EOF
REDDIT_USERNAME=<their username>
REDDIT_PASSWORD=<their password>
REDDIT_AGENT_OBJECTIVE=<their objective, one line>
MAX_COMMENTS_PER_DAY=<their choice or 5>
MIN_COMMENT_INTERVAL_MINUTES=20
QUALITY_THRESHOLD=7
CYCLE_INTERVAL_HOURS=2
LOG_LEVEL=INFO
SCREENSHOT_ON_ERROR=true
EOF
chmod 600 "$INSTALL_DIR/.env"
```

## Step 4: Configure subreddits based on their objective

Edit `$(npm root -g)/reddit-agent/data/subreddits.yaml`.

Based on the user's objective, create a subreddit list with:
- 2-3 **karma building** subreddits (min_karma: 0) — general subs like AskReddit, NoStupidQuestions
- 2-4 **target** subreddits relevant to their objective (min_karma: 20-50)

Each subreddit needs:
- `name`: the subreddit name
- `keywords`: topics relevant to the user's objective
- `max_daily_comments`: 1-3 per sub
- `min_karma`: 0 for easy subs, 20-50 for competitive ones
- `tone`: match the community style
- `notes`: any rules (e.g., "no self-promotion")

Example for someone promoting an AI SaaS:
```yaml
subreddits:
  - name: AskReddit
    keywords: [technology, AI, software]
    max_daily_comments: 2
    min_karma: 0
    tone: "Casual, relatable."
    notes: "Karma building only. No product mentions."

  - name: SaaS
    keywords: [AI tools, automation, growth]
    max_daily_comments: 2
    min_karma: 30
    tone: "Founder-to-founder. Share real experience."
    notes: "OK to mention tools if answering a direct question."

  - name: artificial
    keywords: [AI products, LLM applications]
    max_daily_comments: 2
    min_karma: 20
    tone: "Technical but accessible."
    notes: "Focus on how AI solves real problems."
```

## Step 5: Cookie setup (if on a VM)

If running on a cloud server / VM, Reddit blocks the IP. Ask the user:

> "Reddit blocks cloud server IPs. To bypass this, I need cookies from your browser.
> Please log in to Reddit on your phone or laptop, install the Cookie-Editor extension,
> export cookies for reddit.com, and send me the JSON."

Save cookies to: `$(npm root -g)/reddit-agent/data/cookies.json`

If the user is on a personal computer (not a VM), skip this step.

## Step 6: First run

```bash
reddit-agent run
```

Report the results to the user. Tell them:
- How many subreddits were processed
- How many comments were posted (or why they weren't — karma too low, etc.)
- What the agent learned about the subreddits
- When the next automatic run will happen

## Step 7: Done

The agent now runs every 2 hours automatically. Tell the user:

> "Reddit agent is set up! It will:
> - Post [X] comments per day across [Y] subreddits
> - Build karma automatically on your new account
> - Learn from feedback and improve over time
> - You can ask me anytime: 'How's Reddit doing?' or 'Run the Reddit bot'"

## Ongoing commands

| User says | What to do |
|---|---|
| "Run the Reddit bot" | `reddit-agent run` then report |
| "How's Reddit doing?" | `reddit-agent digest` then summarize |
| "Add r/whatever" | Edit subreddits.yaml |
| "Post more/less" | Edit MAX_COMMENTS_PER_DAY in .env |
| "Stop posting" | Set MAX_COMMENTS_PER_DAY=0 |
| "What did it learn?" | `cat $(npm root -g)/reddit-agent/data/learnings.md` |
| "Change my objective" | Edit REDDIT_AGENT_OBJECTIVE in .env + update subreddits.yaml |
| "Update the agent" | `reddit-agent update` |
