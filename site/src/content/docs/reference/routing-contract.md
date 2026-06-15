---
title: Routing Contract
description: The stable output format every workflow skill router should use.
---

## Complex work

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

## Simple work

```text
No extra routing needed: reason
```

## Route rules

- Select at most four skills.
- Select exactly one primary skill.
- Add supporting skills only when they cover distinct jobs.
- Prefer connectors when live external state is the source of truth.
- Split work into stages when more than four skills seem useful.

## Good route

```text
Route: GitHub / PR comments > Address feedback > Remote review
Use SKILL: github-review-comments, code-review, local-editing, test-runner
Reason: github-review-comments fetches unresolved feedback; code-review evaluates it; local-editing applies changes; test-runner verifies behavior.
```

## Noisy route

```text
Use SKILL: github, code-review, ci, devops, docs, browser, release, planning
```

This route is too broad and should be split by work stage.

