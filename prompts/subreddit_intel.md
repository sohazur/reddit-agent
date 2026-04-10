You are analyzing a subreddit to understand its culture, rules, and engagement patterns.

## Subreddit: r/{{subreddit_name}}

## Recent Top Posts (titles and scores)
{{top_posts}}

## Sample Comments (from high-scoring posts)
{{sample_comments}}

## Sidebar / Rules (if available)
{{sidebar_rules}}

## Your Task

Produce an intelligence report for this subreddit. This will be used by an engagement agent to write better comments.

Respond with ONLY a JSON object:
```json
{
  "tone": "<1-2 sentences describing the dominant tone and writing style>",
  "avg_comment_length": "<e.g. '1-2 sentences' or '1 paragraph'>",
  "hot_topics": ["<topic 1>", "<topic 2>", "<topic 3>"],
  "what_gets_upvoted": "<1 sentence>",
  "what_gets_downvoted": "<1 sentence>",
  "self_promotion_tolerance": "<low/medium/high>",
  "mod_activity": "<low/medium/high based on removed comments>",
  "best_engagement_style": "<1-2 sentences of tactical advice for commenting>",
  "avoid": ["<thing to avoid 1>", "<thing to avoid 2>"]
}
```
