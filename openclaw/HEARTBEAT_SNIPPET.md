# Reddit Agent Heartbeat Tasks

Add these to your HEARTBEAT.md to have your OpenClaw agent manage Reddit automatically:

```markdown
## Reddit Agent
- [ ] Run reddit-agent cycle if last run was >2h ago
- [ ] Check reddit-agent --feedback for past comment performance
- [ ] If any CRITICAL alerts (shadowban, high removal rate), pause the agent and notify me
- [ ] On first heartbeat of the day, run reddit-agent --digest
```
