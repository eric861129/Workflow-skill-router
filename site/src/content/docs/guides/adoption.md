---
title: Customization Guide
description: Adapt Workflow Skill Router to your own agent skill catalog.
---

## Start with the starter

Copy `starter/workflow-skill-router/` into your agent's skill directory. The starter gives you the output contract, route shape, and reference files to fill.

Workflow Skill Router addresses skill selection sprawl, not authorization. Keep your existing scope contracts, runtime permissions, approval policies, and tool access controls in place.

## Inventory your skills

Group skills by source:

- local custom skills
- connector or plugin skills
- system skills
- meta workflow skills
- file-format skills

Mark skills that are likely to over-trigger, especially broad writing, design, planning, and meta workflow skills.

## Write conflict rules

Conflict rules are the main value of the router.

Common conflicts:

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## Share examples responsibly

Use fictional company-style examples when sharing routers. Do not include:

- real repository paths
- internal project names
- customer names
- hostnames, tokens, and secrets
- deployment branch names
- regulated data details

Use placeholders such as `Acme Corp`, `Customer Portal`, `Internal Admin`, `Revenue Platform`, and `Operations Dashboard`.

## Source

- [View starter router](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [View adoption guide source](https://github.com/eric861129/Workflow-skill-router/blob/main/docs/adoption-guide.md)
- [View prompts](https://github.com/eric861129/Workflow-skill-router/tree/main/prompts)

