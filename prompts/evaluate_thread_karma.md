You are picking a Reddit thread to comment on for karma building. The goal is NOT to promote anything. The goal is to write a helpful, genuine comment that people will upvote.

## Subreddit: r/{{subreddit_name}}
Tone: {{subreddit_tone}}

## Thread to Evaluate

**Title:** {{thread_title}}
**Body:** {{thread_body}}
**Score:** {{thread_score}} | **Comments:** {{thread_comment_count}}
**Top comments (sample):**
{{thread_comments}}

## Score this thread 1-10 for karma-building potential:

- **Popularity (0-3):** Is this a popular/trending thread where comments get seen? High score = more upvote potential.
- **Answerability (0-3):** Can we add a genuinely helpful, interesting, or funny response? Is there room for a new perspective?
- **Safety (0-2):** Is this a safe topic? Avoid controversial, political, sensitive, or NSFW content.
- **Freshness (0-2):** Is the thread fresh enough that a new comment won't be buried?

Respond with ONLY a JSON object:
```json
{
  "popularity": <0-3>,
  "answerability": <0-3>,
  "safety": <0-2>,
  "freshness": <0-2>,
  "total": <sum>,
  "reasoning": "<one sentence>"
}
```
