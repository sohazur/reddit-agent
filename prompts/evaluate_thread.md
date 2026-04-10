You are evaluating whether a Reddit thread is a good opportunity for engagement.

## Your Objective
{{objective}}

## Subreddit: r/{{subreddit_name}}
Tone guidance: {{subreddit_tone}}
Community notes: {{subreddit_notes}}

## Thread to Evaluate

**Title:** {{thread_title}}
**Body:** {{thread_body}}
**Score:** {{thread_score}} | **Comments:** {{thread_comment_count}}
**Top comments (sample):**
{{thread_comments}}

## Your Task

Score this thread 1-10 on engagement opportunity:

- **Relevance (0-3):** How related is this to your objective and expertise?
- **Opportunity (0-3):** Is there a natural opening to contribute meaningfully? Would a knowledgeable comment be welcome?
- **Risk (0-2):** Is this thread hostile to outsiders? Are mods active? Could your presence backfire?
- **Timing (0-2):** Is this thread still active? Fresh enough that a comment would be seen?

Respond with ONLY a JSON object:
```json
{
  "relevance": <0-3>,
  "opportunity": <0-3>,
  "risk": <0-2>,
  "timing": <0-2>,
  "total": <sum>,
  "reasoning": "<one sentence explaining your score>"
}
```
