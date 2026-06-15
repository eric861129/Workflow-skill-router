# Anti-Over-Routing Guide

Workflow Skill Router is useful because it chooses fewer skills than a flat keyword match would choose.

## The Rule

Start with one primary skill. Add a supporting skill only when it reduces a specific risk that the primary skill does not cover.

Good supporting skills answer one of these questions:

- What domain knowledge is missing?
- What verification path is needed?
- What live source of truth must be queried?
- What handoff or release step is genuinely part of this task?

## Do Not Route By Keyword Alone

Related words are not enough. A request that mentions "docs", "CI", "GitHub", "database", or "browser" should not automatically activate every matching skill.

Example:

```text
User: Fix a typo in the database migration guide.

Good route: code-documenter
Bad route: code-documenter, database-optimizer, sql-pro, devops-engineer
```

The database words describe the document topic, not the work being performed.

## Use Connector Skills Late

Connector skills are most valuable when live external state is the source of truth.

Use a connector when the task requires:

- current PR comments,
- current CI run logs,
- current issue metadata,
- repository settings that cannot be inferred from local files.

Do not add a connector just because the work will eventually be pushed to GitHub.

## Split Work Instead Of Loading Everything

If a route needs more than four skills, split it into stages:

```text
Stage 1: API contract design
Use SKILL: api-designer, openapi-contract-generation-skill

Stage 2: Frontend client update
Use SKILL: openapi-to-typescript, vue-expert

Stage 3: Verification
Use SKILL: qa-test-planner, playwright
```

The staged route is easier to review and less likely to mix incompatible instructions.

## Supporting Skill Checklist

Before adding a supporting skill, ask:

- Does it change the next action?
- Does it reduce a concrete risk?
- Does it own a distinct domain or verification path?
- Would the route still be correct without it?

If the last answer is yes, leave the skill out.
