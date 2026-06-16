---
name: workflow-skill-router
description: Route complex AI agent tasks to the smallest useful skill set before work starts. Use when a task may involve multiple skills, tools, connectors, work stages, or overlapping workflows, and the agent should classify the request, choose one primary skill plus up to three supporting skills, and explain the route before continuing.
---

# Workflow Skill Router

## Purpose

Use this as a thin routing layer before substantial work. It maps the user's request from task nature to work stage, technical domain, and a small skill set.

The router addresses skill selection sprawl. It does not replace the selected skills, scope contracts, runtime permissions, approval policies, or tool access controls. It only chooses and explains which already-available skills should be active.

## Routing Workflow

1. Classify the request into `task nature > work stage > technical domain`.
2. Read `references/skill-tree.md` when the mapping is not obvious.
3. Read `references/routing-rules.md` when skills overlap, the task names a connector, or more than four skills seem relevant.
4. Select one primary skill and up to three supporting skills.
5. State the route before starting substantial work.

## Output Contract

For routed work:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

For simple work:

```text
No extra routing needed: reason
```

Then continue with the actual task.

## Selection Rules

- Select at most four skills.
- Use the displayed skill names exactly.
- Prefer connector or plugin skills when live external systems are the source of truth.
- Prefer local/custom skills for repository-specific engineering judgment.
- Do not use broad meta workflow skills by default.
- If the user names a skill, keep it unless unavailable and add only necessary supporting skills.
- If more than four skills seem useful, split the work into stages.

## References

- `references/skill-tree.md`: task-stage-domain route map.
- `references/routing-rules.md`: priority, conflict handling, and examples.
