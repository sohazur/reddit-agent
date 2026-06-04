You are mapping out where on Reddit the ideal customers of {{company_name}} hang
out and ask for help.

{{company_one_liner}}

What we do (services):
{{services_block}}

Who we serve: {{audiences}}
Objective: {{objective}}

Already tracking these subreddits (don't repeat them): {{known_subreddits}}

List subreddits where people regularly describe problems our services solve, or
where our target audiences gather. Favor communities with real
questions/frustrations over giant generic subs. Give a relevance 1-10 (10 = our
buyers are clearly here asking for exactly what we do).

Return ONLY a JSON array (no prose), each item:
```json
[
  {"name": "SEO", "relevance": 9, "rationale": "one short reason"},
  {"name": "smallbusiness", "relevance": 6, "rationale": "..."}
]
```
Use the subreddit name only, without the "r/". Return up to 15.
