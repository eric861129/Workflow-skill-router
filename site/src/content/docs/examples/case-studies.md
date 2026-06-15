---
title: Routing Case Studies
description: Six examples that turn fuzzy requests into small, reviewable routes.
---

These case studies show the pattern behind Workflow Skill Router: avoid loading every related skill, then choose one primary skill plus focused support.

## API contract sync

Fuzzy request:

```text
Add a customer settings endpoint, update OpenAPI, regenerate the frontend client, and make sure the contract is tested.
```

Bad over-route:

```text
Use SKILL: backend-developer, api-designer, openapi-contract-generation-skill, openapi-to-typescript, database-optimizer, qa-test-planner, frontend-design
```

Better route:

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
Reason: api-designer owns endpoint semantics; openapi-contract-generation-skill manages schema change; openapi-to-typescript updates client types; qa-test-planner defines contract coverage.
```

Why smaller is better: the route keeps one owner for API shape and adds only the tools needed to propagate and verify the contract.

## Vue browser regression

Fuzzy request:

```text
A Vue form loses selected values after refresh. Reproduce it in the browser and add a regression check.
```

Bad over-route:

```text
Use SKILL: vue-expert, frontend-design, browser, playwright, qa-test-planner, api-designer, database-optimizer
```

Better route:

```text
Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: vue-expert, systematic-debugging, playwright, qa-test-planner
Reason: vue-expert handles component state; systematic-debugging isolates the cause; playwright captures the browser regression; qa-test-planner defines acceptance coverage.
```

Why smaller is better: the route starts where the symptom appears, adds causal debugging, and saves the repeatable browser check for verification.

## PR review plus CI repair

Fuzzy request:

```text
Review this auth-related PR, address review feedback, and fix the failing CI checks before merge.
```

Bad over-route:

```text
Use SKILL: github, receiving-code-review, security-review, systematic-debugging, qa-test-planner, devops-engineer, commit-work, documentation-writer
```

Better route:

```text
Route: Review / CI readiness > Security-sensitive change
Use SKILL: receiving-code-review, systematic-debugging, qa-test-planner, commit-work
Reason: receiving-code-review turns feedback into action; systematic-debugging isolates CI failures; qa-test-planner protects the auth surface; commit-work prepares a clean final commit.
```

Why smaller is better: the route focuses on pre-merge work. Connector skills can be added only when live GitHub comments or logs are the source of truth.

## Documentation source-map cleanup

Fuzzy request:

```text
The docs source map is stale after moving guide pages. Fix the public links and make sure each page still points to the right source file.
```

Bad over-route:

```text
Use SKILL: code-documenter, spec-miner, frontend-design, devops-engineer, qa-test-planner, github
```

Better route:

```text
Route: Documentation / Source map > Link and provenance cleanup
Use SKILL: code-documenter, spec-miner
Reason: code-documenter owns developer-facing wording; spec-miner checks where the docs are sourced from.
```

Why smaller is better: the route stays focused on content and provenance. Site build or GitHub connector skills can be added later only if validation fails or live repo state is required.

## Database migration with performance risk

Fuzzy request:

```text
Add audit tables for account changes and make sure the admin activity query stays fast after the migration.
```

Bad over-route:

```text
Use SKILL: database-schema-designer, sql-pro, database-optimizer, devops-engineer, api-designer, qa-test-planner, frontend-design
```

Better route:

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer owns table shape; sql-pro keeps SQL clear; database-optimizer checks query cost; qa-test-planner defines migration coverage.
```

Why smaller is better: the selected skills cover schema, SQL, performance, and verification without distracting the agent with unrelated API or UI work.

## Release plus connector closeout

Fuzzy request:

```text
Finish the release branch, check the latest GitHub run, and prepare the release note.
```

Bad over-route:

```text
Use SKILL: finishing-a-development-branch, github, receiving-code-review, systematic-debugging, devops-engineer, code-documenter, commit-work
```

Better route:

```text
Route: Release / Closeout > GitHub-backed readiness check
Use SKILL: finishing-a-development-branch, github, code-documenter
Reason: finishing-a-development-branch owns the local finish line; github checks live run state; code-documenter prepares the release note.
```

Why smaller is better: the connector is included because live GitHub state is the source of truth. Debugging and DevOps skills remain inactive unless the run fails.
