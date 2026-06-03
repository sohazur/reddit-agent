You are picking a Reddit thread to comment on for karma building. The goal is NOT to promote anything. The goal is to write a helpful, genuine comment that people will upvote.

## Subreddit: r/{{subreddit_name}}
Tone: {{subreddit_tone}}

## Thread to Evaluate

**Title:** {{thread_title}}
**Body:** {{thread_body}}
**Score:** {{thread_score}} | **Comments:** {{thread_comment_count}}
**Top comments (sample):**
{{thread_comments}}

## HARD EXCLUSIONS — score total 0 if ANY apply

This account is being built as a credible, knowledgeable voice. Set
`"total": 0` (UNCONDITIONALLY — do not rationalize that "a factual answer is
still possible") and name the exclusion if the thread's TOPIC touches ANY of:

- **Health / medical / bodily / gynecological / pregnancy / mental-health.**
- **Sex, dating, relationships, marriage, gender, or identity.**
- **Politics, religion, race, or any divisive/controversial culture topic.**
- **NSFW, violence, tragedy, trauma, or crisis.**
- Anything where commenting invites a **personal anecdote** ("as a woman…",
  "my ex…", "when I was…") or where the popular answers are personal stories.
- Threads that only reward **ragebait, hot-takes, or mocking** someone.

These are zero regardless of how popular or "answerable" they look. A stray
comment in any of these does more reputational harm than the karma is worth.

Prefer neutral, factual, practical, or knowledge-based threads — the kind a
level-headed, informed person answers without revealing personal identity.

## Otherwise, score this thread 1-10 for karma-building potential:

- **Popularity (0-3):** Is this a popular/trending thread where comments get seen? High score = more upvote potential.
- **Answerability (0-3):** Can we add a genuinely helpful, interesting, or factual response WITHOUT inventing personal experience? Is there room for a new perspective?
- **Safety (0-2):** Is this a safe, non-sensitive, non-divisive topic (after the hard exclusions above)?
- **Freshness (0-2):** Is the thread fresh enough that a new comment won't be buried?

Respond with ONLY a JSON object:
```json
{
  "popularity": <0-3>,
  "answerability": <0-3>,
  "safety": <0-2>,
  "freshness": <0-2>,
  "total": <sum, or 0 if a hard exclusion fired>,
  "reasoning": "<one sentence; name the exclusion if total is 0>"
}
```
