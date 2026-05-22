---
name: workflow-skill-router
description: Use when complex agent tasks need the right SKILL set selected before work starts, especially multi-domain development, architecture, docs, UI, debugging, review, deployment, data, connector, or skill-management workflows.
---

# Workflow Skill Router

## Overview

Use this as a light routing layer before substantial work. It maps the user's request from task nature to work stage, technical domain, and a small SKILL set.

The goal is not to load every related skill. Pick the smallest useful set, then work normally.

## When To Use

Use this skill for:

- New features, refactors, architecture decisions, API/backend/database work.
- Frontend, UI/UX, browser debugging, or rendered-app verification.
- Documentation, diagramming, file-format, connector, CI, deployment, or data workflows.
- Review, bug investigation, legacy-system archaeology, prompt-library work, or skill creation.
- Any task where several SKILLs might apply and a quick routing decision prevents noise.

Do not use this skill for:

- One-line shell commands, simple factual answers, translation, or tiny edits.
- A narrow task where the user explicitly named one SKILL and no supporting SKILL is needed.
- Cases where a more specific system/plugin skill has already been explicitly invoked.

## Routing Workflow

1. Classify the request into `task nature > work stage > technical domain`.
2. Read `references/skill-tree.md` only when the mapping is not obvious.
3. Read `references/routing-rules.md` when multiple skills overlap, the request names a connector, or more than four skills seem relevant.
4. Select one primary SKILL and up to three supporting SKILLs.
5. Before starting substantial work, state the route using the output contract below.

## Output Contract

For routed work, say:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

For simple work, say:

```text
No extra routing needed: reason
```

Then continue with the actual task.

## Selection Rules

- Select at most four SKILLs.
- Prefer local custom SKILLs for general engineering guidance.
- Prefer plugin/connector SKILLs when the task needs a live external system or runtime.
- Do not use broad meta SKILLs by default.
- If the user names a SKILL, keep it and add only necessary supporting SKILLs.

## References

- `references/skill-tree.md`: full task-stage-domain SKILL map.
- `references/routing-rules.md`: conflict handling, priority, and examples.
