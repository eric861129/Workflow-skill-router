# Routing Showcase

Five shareable before/after examples for explaining why Workflow Skill Router exists.

## 60-second Demo

![60-second Workflow Skill Router demo](assets/workflow-skill-router-60s-demo.gif)

## 1. API Contract Sync

### Before

```text
User: Add a customer settings endpoint, update OpenAPI, regenerate the frontend client, and test the contract.

Over-route: backend-developer, api-designer, openapi-contract-generation-skill, openapi-to-typescript, database-optimizer, frontend-design, qa-test-planner
```

### After

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
Reason: Design the endpoint, update the schema, regenerate client types, and verify the contract without pulling in unrelated performance or visual design work.
```

## 2. Vue Browser Regression

### Before

```text
User: A Vue form loses selected values after refresh. Reproduce it in the browser and add a regression check.

Over-route: vue-expert, frontend-design, browser, playwright, qa-test-planner, api-designer, database-optimizer
```

### After

```text
Route: Frontend / Vue / UI > Browser regression > State persistence
Use SKILL: vue-expert, systematic-debugging, playwright, qa-test-planner
Reason: Keep the route at the rendered symptom, isolate the cause, capture the browser check, and define acceptance coverage.
```

## 3. Documentation Source-Map Cleanup

### Before

```text
User: The docs source map is stale after moving guide pages. Fix the links and make sure the public docs still point to the right source files.

Over-route: code-documenter, spec-miner, frontend-design, devops-engineer, qa-test-planner, github
```

### After

```text
Route: Documentation / Source map > Link and provenance cleanup
Use SKILL: code-documenter, spec-miner
Reason: code-documenter owns the public docs wording; spec-miner checks source provenance. No deployment or design skill is needed unless the site build fails.
```

## 4. Database Migration With Performance Risk

### Before

```text
User: Add audit tables for account changes and make sure the admin activity query stays fast after the migration.

Over-route: database-schema-designer, sql-pro, database-optimizer, devops-engineer, api-designer, qa-test-planner, frontend-design
```

### After

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: Model the schema, review SQL, check query cost, and protect migration behavior without involving API or UI work.
```

## 5. Release Plus Connector Closeout

### Before

```text
User: Finish the release branch, check the latest GitHub run, and prepare the release note.

Over-route: finishing-a-development-branch, github, receiving-code-review, systematic-debugging, devops-engineer, code-documenter, commit-work
```

### After

```text
Route: Release / Closeout > GitHub-backed readiness check
Use SKILL: finishing-a-development-branch, github, code-documenter
Reason: Finish the branch, use GitHub only for live run state, and write release notes. Debugging and DevOps stay out unless the run fails.
```
