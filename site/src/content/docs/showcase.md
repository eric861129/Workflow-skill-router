---
title: Routing Showcase
description: Seven shareable before-and-after examples for Workflow Skill Router.
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

<!-- M4-B adaptive-memory-reference:start -->
## Adaptive Workflow Memory public contract

The public surface contains **20** MCP tools. Memory uses a separate **Operational DB** and **Optional Memory DB**. Managed writes are limited to `managed-personal` and `managed-workspace-local`; User-owned Profile writes still require their original authority.

The four decisions remain separate: policy autonomy, trusted Workspace binding, Profile ownership/target authority, and Runtime/Side-effect execution authority. A trusted root is not a Host write grant.

**Skill consistency** is **unavailable** without **receipt evidence**. A planned route may be `intended-unverified`; it is not activation proof. The Memory Flight Recorder uses `fixture-trace` or sanitized runtime records. Its `deterministic-local-pilot` is **not Model Evidence** and never contains actual Personal Memory.

### Flight Recorder and Pilot

The homepage presents five read-only sanitized scenarios—Policy Resolution, Observe, Reviewed Proposal, Automatic Managed Promotion and Purge—plus twenty deterministic local Pilot records: 6 Single, 8 Phased and 6 Goal-like, with at least eight Profile-assisted cases. The display is evidence literacy, not a product-performance claim.
<!-- M4-B adaptive-memory-reference:end -->
