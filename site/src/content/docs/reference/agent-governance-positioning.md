---
title: Agent Governance Positioning
description: Where Workflow Skill Router fits in agent sprawl and agent governance.
---

Workflow Skill Router addresses one layer of agent sprawl: **skill selection sprawl**.

It does not replace scope contracts, runtime permissions, approval policies, or tool access controls. Instead, it gives agents a small, reviewable routing decision before work starts.

## What problem it handles

As an agent environment grows, the number of available skills, tools, connectors, and workflows grows with it. A broad task can then trigger too many related instructions at once:

```text
frontend, ui, browser, playwright, qa, design-system, github, docs, deployment
```

Workflow Skill Router narrows that list before execution. It asks the agent to choose:

- one Primary skill,
- only the Supporting skills that reduce risk or add required context,
- the skills that look related but should stay out,
- a short reason for the route.

## What it does not handle

Workflow Skill Router is not a security boundary.

Use your existing governance layers for:

- scope contracts,
- runtime permissions,
- approval policies,
- tool access controls,
- sandboxing,
- secret handling,
- external system authorization.

The router assumes a skill is already available and allowed. It only decides whether that skill is useful for the current task.

## Why this layer matters

Skill selection is small enough to review before the agent edits files or calls tools. That makes it useful as an early checkpoint:

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: vue-expert, systematic-debugging, playwright
Reason: vue-expert handles component behavior; systematic-debugging keeps the investigation causal; playwright captures the regression.
```

The user can correct this decision before execution begins.

## Recommended governance stack

Workflow Skill Router fits best as a pre-execution layer:

```text
Task request
  -> Scope contract
  -> Skill selection route
  -> Runtime permissions
  -> Tool approvals
  -> Execution and verification
```

This keeps the project honest: it controls instruction selection, not authorization.

