---
title: Routing Showcase
description: Five shareable before-and-after examples for Workflow Skill Router.
---

The V2 homepage includes seven inspectable scenarios for Single, Phased, Managed Goal, Explicit Skill Lock, consent, verified-host scheduling, and model evaluation. Each scenario renders the sanitized JSONL request and response produced by the Router bridge. The browser displays those results; it does not recompute them.

## Read the Flight Recorder

- `runtime-trace` runs against the bundled local R0 control plane. `plan_work` and `get_router_status` work locally.
- The local Managed Goal trace returns `capability-unavailable` for `get_next_work`. It never invents a local scheduler result.
- `fixture-trace` runs through the full Router service composition with verified-host fixture ports. It proves the host contract, not a production host connection.
- Explicit Skill Lock asks before activating recommended support. A rejected Skill remains in the audit trail and stays out of active selections.
- Model evaluation remains `manual-required` until an authorized fresh-model run exists. Every public result still passes a `review-required` publication gate.

**Tier 0 Contract** remains separate from Behavior evidence. The UI never upgrades local planning or `skill-only-fallback` into `hybrid-full`.

Use these examples when explaining the project in a post, issue, or README snippet.

## Visual preview

This video is a lightweight visual accent for the page, not an interactive demo or a product walkthrough. The actual route before-and-after examples are below.

<video controls muted playsinline preload="none" poster="/Workflow-skill-router/assets/workflow-skill-router-demo-poster.webp" width="1280" height="720">
  <source src="/Workflow-skill-router/assets/workflow-skill-router-demo.webm" type="video/webm" />
  <source src="/Workflow-skill-router/assets/workflow-skill-router-demo.mp4" type="video/mp4" />
  <a href="/Workflow-skill-router/assets/workflow-skill-router-demo.mp4">Open the visual preview video</a>
</video>

## API contract sync

Before:

```text
Over-route: backend-developer, api-designer, openapi-contract-generation-skill, openapi-to-typescript, database-optimizer, frontend-design, qa-test-planner
```

After:

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
```

## Vue browser regression

Before:

```text
Over-route: vue-expert, frontend-design, browser, playwright, qa-test-planner, api-designer, database-optimizer
```

After:

```text
Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: vue-expert, systematic-debugging, playwright, qa-test-planner
```

## Documentation source-map cleanup

Before:

```text
Over-route: code-documenter, spec-miner, frontend-design, devops-engineer, qa-test-planner, github
```

After:

```text
Route: Documentation / Source map > Link and provenance cleanup
Use SKILL: code-documenter, spec-miner
```

## Database migration with performance risk

Before:

```text
Over-route: database-schema-designer, sql-pro, database-optimizer, devops-engineer, api-designer, qa-test-planner, frontend-design
```

After:

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
```

## Release plus connector closeout

Before:

```text
Over-route: finishing-a-development-branch, github, receiving-code-review, systematic-debugging, devops-engineer, code-documenter, commit-work
```

After:

```text
Route: Release / Closeout > GitHub-backed readiness check
Use SKILL: finishing-a-development-branch, github, code-documenter
```
