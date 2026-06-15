---
name: generic-agent-router
description: Route generic multi-skill AI agent tasks before work starts. Use when the agent has a small catalog of planning, coding, debugging, documentation, review, connector, or release skills and should select one primary skill plus up to three supporting skills.
---

# Generic Agent Router

Classify the task, choose a small skill set, explain the route, then continue.

## Workflow

1. Classify the task as `task nature > work stage > technical domain`.
2. Use `references/skill-tree.md` for route selection.
3. Use `references/routing-rules.md` when skills overlap.
4. Select one Primary skill and up to three Supporting skills.
5. Emit the routing output before doing substantial work.

## Output

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill
Reason: one short sentence per SKILL
```

For one-step work:

```text
No extra routing needed: reason
```

