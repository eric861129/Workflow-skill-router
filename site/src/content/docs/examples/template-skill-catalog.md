---
title: Template Skill Catalog
description: A single public-safe example catalog that mirrors the Reference Template package.
---

This example is the fastest way to understand the Reference Template. It shows which public-safe skills are included and how they can be routed in practical engineering work. Use it as a model for designing your own router, not as a catalog you need to copy as-is.

- [Download the Reference Template](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip)
- [Download the Full source archive](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [View the template source folder](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [Open the template sample routes](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/sample-routes.md)

## Complete Case Studies

These examples show the full route from user prompt to the skill set an agent should load.

### API contract sync

User prompt:

```text
Add a customer settings endpoint, update OpenAPI, regenerate the TypeScript client, and define the contract tests.
```

Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: `api-designer`, `openapi-contract-generation-skill`, `openapi-to-typescript`, `qa-test-planner`
Reason: `api-designer` stabilizes endpoint semantics; `openapi-contract-generation-skill` manages schema diff and generation; `openapi-to-typescript` updates frontend types; `qa-test-planner` defines contract coverage.

### Database migration with performance risk

User prompt:

```text
Add audit tables for account changes and make sure the admin activity query stays fast after the migration.
```

Route: Database / Schema and performance > Migration plus query review
Use SKILL: `database-schema-designer`, `sql-pro`, `database-optimizer`, `qa-test-planner`
Reason: `database-schema-designer` models the audit tables; `sql-pro` keeps queries clear; `database-optimizer` checks runtime cost; `qa-test-planner` covers migration and regression scenarios.

### Browser-only Vue regression

User prompt:

```text
A Vue form loses selected values after refresh. Reproduce it in the browser and add a regression check.
```

Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: `vue-expert`, `systematic-debugging`, `playwright`, `qa-test-planner`
Reason: `vue-expert` handles component and reactivity behavior; `systematic-debugging` finds the real cause; `playwright` captures a repeatable browser check; `qa-test-planner` defines acceptance coverage.

### PR review and CI repair

User prompt:

```text
Review an auth-related PR, address review feedback, and fix the failing CI checks before merge.
```

Route: Review / CI readiness > Security-sensitive change
Use SKILL: `receiving-code-review`, `systematic-debugging`, `qa-test-planner`, `commit-work`
Reason: `receiving-code-review` turns feedback into action; `systematic-debugging` isolates CI failures; `qa-test-planner` protects the auth surface; `commit-work` prepares a clean final commit.

### Architecture notes to handoff

User prompt:

```text
Turn a system design discussion into a C4 diagram, implementation plan, and handoff notes.
```

Route: Architecture / Documentation > Decision record and handoff
Use SKILL: `architecture-designer`, `c4-architecture`, `code-documenter`, `session-handoff`
Reason: `architecture-designer` frames the decision; `c4-architecture` creates readable diagrams; `code-documenter` turns it into developer docs; `session-handoff` captures next-step context.

### Dependency upgrade with release risk

User prompt:

```text
Upgrade the frontend build dependencies, identify regression risk, and prepare the branch for release.
```

Route: DevOps / Dependency / Release > Safe upgrade path
Use SKILL: `dependency-updater`, `systematic-debugging`, `qa-test-planner`, `finishing-a-development-branch`
Reason: `dependency-updater` plans the upgrade; `systematic-debugging` handles breakages; `qa-test-planner` maps regression risk; `finishing-a-development-branch` checks release readiness.

## Bad Route vs Better Route

These examples show what the router is trying to prevent: overloading context with every related skill instead of selecting the smallest useful working set.

### Frontend bug

User prompt:

```text
The customer dashboard is blank after login. Reproduce the issue and fix it.
```

Bad route:

```text
Route: Frontend / Everything related > Dashboard problem
Use SKILL: `frontend-design`, `ui-styling`, `vue-expert`, `playwright`, `qa-test-planner`, `devops-engineer`
Reason: These skills are all related to web work.
```

Better route:

```text
Route: Frontend / Vue / UI > Logged-in browser regression
Use SKILL: `vue-expert`, `systematic-debugging`, `playwright`
Reason: `vue-expert` handles component and state behavior; `systematic-debugging` finds whether the blank page comes from data, auth, or rendering; `playwright` captures a repeatable browser check.
```

### API and frontend type drift

User prompt:

```text
The API renamed a response field and the frontend now has type errors. Sync the contract and update the client.
```

Bad route:

```text
Route: Backend / Frontend / Testing / Docs > Contract change
Use SKILL: `csharp-developer`, `vue-expert`, `database-schema-designer`, `code-documenter`, `qa-test-planner`
Reason: This touches many parts of the stack.
```

Better route:

```text
Route: API / Contract lifecycle > Schema diff and client generation
Use SKILL: `openapi-contract-generation-skill`, `openapi-to-typescript`, `api-designer`, `qa-test-planner`
Reason: `openapi-contract-generation-skill` owns the schema diff; `openapi-to-typescript` updates client types; `api-designer` checks compatibility; `qa-test-planner` defines regression coverage.
```

## Requirements / Planning / Task Breakdown

- Requirements / Clarification / Complex feature: Primary: `requirements-clarity`; Supporting: `writing-clearly-and-concisely`, `spec-miner`
- Planning / Implementation plan / Multi-stage engineering: Primary: `executing-plans`; Supporting: `karpathy-guidelines`, `qa-test-planner`
- Handoff / Branch completion / Delivery notes: Primary: `session-handoff`; Supporting: `finishing-a-development-branch`, `commit-work`

## Architecture / API / Backend

- Architecture / System design / High-level decision: Primary: `architecture-designer`; Supporting: `c4-architecture`, `cloud-architect`
- API / REST governance / Naming, pagination, versioning, errors: Primary: `api-guidelines-skill`; Supporting: `api-designer`, `openapi-contract-generation-skill`
- API / OpenAPI sync / Schema diff and client generation: Primary: `openapi-contract-generation-skill`; Supporting: `openapi-to-typescript`, `api-designer`
- Backend / C# or .NET / Service implementation: Primary: `csharp-developer`; Supporting: `dotnet-core-expert`, `database-schema-designer`, `qa-test-planner`

## Database / SQL

- Database / Schema / Migration: Primary: `database-schema-designer`; Supporting: `sql-pro`, `database-optimizer`
- Database / Performance / Slow query: Primary: `database-optimizer`; Supporting: `sql-pro`, `systematic-debugging`
- Data contract / API and DB boundary: Primary: `api-designer`; Supporting: `openapi-to-typescript`, `database-schema-designer`

## Frontend / Vue / UI

- Frontend / Vue component / New feature page: Primary: `vue-expert`; Supporting: `vue-composition-patterns-skill`, `frontend-design`
- Frontend / Shared state / Composition API refactor: Primary: `vue-composition-patterns-skill`; Supporting: `vue-expert`, `systematic-debugging`
- Frontend / Product UI / Public-facing page: Primary: `frontend-design`; Supporting: `ui-ux-pro-max`, `ui-styling`
- Frontend / Screenshot to implementation / Visual matching: Primary: `image-to-code-skill`; Supporting: `frontend-design`, `tailwind-design-token-skill`

## Design System / Visual Quality

- Design system / Tokens and primitives / Starter setup: Primary: `design-system-starter`; Supporting: `design-system`, `tailwind-design-token-skill`, `storybook-design-system-skill`
- Storybook / Component states / Visual review: Primary: `storybook-design-system-skill`; Supporting: `frontend-design`, `qa-test-planner`
- UI redesign / Premium polish / Existing project: Primary: `redesign-skill`; Supporting: `gpt-tasteskill`, `ui-ux-pro-max`
- Minimal interface / Editorial clarity / Quiet docs UI: Primary: `minimalist-skill`; Supporting: `ui-styling`, `frontend-design`

## Debugging / Testing / Browser

- Debugging / Unknown failure / Causal investigation: Primary: `systematic-debugging`; Supporting: `playwright`, `qa-test-planner`
- Browser QA / Regression / Repeatable interaction: Primary: `playwright`; Supporting: `qa-test-planner`, `systematic-debugging`
- Test planning / Acceptance coverage / Release confidence: Primary: `qa-test-planner`; Supporting: `receiving-code-review`, `systematic-debugging`

## Documentation / Diagrams / Specification

- Documentation / Technical guide / Developer-facing docs: Primary: `code-documenter`; Supporting: `mermaid-diagrams`, `c4-architecture`
- Specification / Existing system discovery / Behavior extraction: Primary: `spec-miner`; Supporting: `code-documenter`, `architecture-designer`
- Coauthoring / User-facing guide / Collaborative writing: Primary: `doc-coauthoring`; Supporting: `writing-clearly-and-concisely`, `code-documenter`
- PDF / Document review / File deliverable: Primary: `pdf`; Supporting: `code-documenter`, `file-organizer`
- Agent docs / Large instruction file / Refactor and cleanup: Primary: `agent-md-refactor`; Supporting: `writing-clearly-and-concisely`, `code-documenter`

## DevOps / Dependency / Release

- Local dev / Docker Compose / Service stack: Primary: `docker-compose-local-dev-skill`; Supporting: `devops-engineer`, `dependency-updater`
- Dependencies / Upgrade / Risk and regression: Primary: `dependency-updater`; Supporting: `systematic-debugging`, `qa-test-planner`
- DevOps / Deployment planning / Cloud readiness: Primary: `devops-engineer`; Supporting: `cloud-architect`, `docker-compose-local-dev-skill`
- Release / Final verification / Commit readiness: Primary: `finishing-a-development-branch`; Supporting: `commit-work`, `qa-test-planner`

## Brand / Product / Cross-platform

- Brand / Voice and messaging / Product narrative: Primary: `brand`; Supporting: `design`, `banner-design`
- Cross-platform / Flutter app / Mobile implementation: Primary: `flutter-expert`; Supporting: `frontend-design`, `qa-test-planner`
- Product visuals / Web hero assets / Generated concept: Primary: `imagegen-frontend-web`; Supporting: `frontend-design`, `brand`
- Mobile visuals / App concept / Generated screen direction: Primary: `imagegen-frontend-mobile`; Supporting: `flutter-expert`, `ui-ux-pro-max`
- Visual direction / Taste and polish / Product surface: Primary: `design`; Supporting: `soft-skill`, `taste-skill`

## Agent / Skill Management / OpenAI

- Agent routing / Router maintenance / Skill inventory update: Primary: `workflow-skill-router`; Supporting: `skill-creator`, `writing-clearly-and-concisely`
- Skill authoring / New Codex skill / Instruction package: Primary: `skill-creator`; Supporting: `openai-docs`, `code-documenter`
- Plugin packaging / Capability bundle / Installable extension: Primary: `plugin-creator`; Supporting: `skill-installer`, `openai-docs`
- Image generation / General raster asset / Prompted visual: Primary: `imagegen`; Supporting: `imagegen-frontend-web`, `frontend-design`, `brand`

## Source

- [View `examples/template-skill-catalog/`](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [View `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/skill-tree.md)
- [View `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/routing-rules.md)
- [View `references/sample-routes.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/template-skill-catalog/references/sample-routes.md)
