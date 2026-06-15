# Routing Rules

## Priority

1. Prefer platform-specific skills for platform repositories, contracts, RBAC, staging data, incidents, releases, and deployment governance.
2. Prefer connector skills when GitHub, browser, workspace files, or CI systems are the source of truth.
3. Prefer security skills for auth, RBAC, customer data, secrets, file access, public links, and deployment exposure.
4. Prefer generic engineering skills only as supporting skills when they add a distinct job.
5. Use meta workflow skills only when planning, debugging, or release process is the task.

## Conflict Handling

- `platform-api-contract` vs `api-designer`: use platform API contract for platform endpoints, DTOs, envelopes, generated clients, and integration tests; use API designer for broader REST judgment.
- `platform-architecture` vs `platform-clean-code`: use architecture for module boundaries and project references; use clean code for naming, responsibility, comments, and implementation shape.
- `portal-frontend-core` vs `frontend-builder`: use portal frontend core for company app boundaries; use frontend builder for generic UI implementation.
- `frontend-monorepo` vs `portal-frontend-core`: use frontend monorepo for workspace scripts, env modes, proxy, shared packages, and build output.
- `staging-data-verifier` vs `sql-pro`: use staging data verifier when live data, RBAC, menu, or environment differs from code; use SQL skills for query quality.
- `incident-response` vs `systematic-debugging`: use incident response to stabilize and decide rollback or hotfix; use systematic debugging to find root cause.
- `deployment-governance` vs `platform-release-checklist`: use deployment governance for promotion, artifacts, rollback, and approvals; use release checklist for local readiness.

## Output Examples

```text
Route: Sync / Backend to frontend > API schema and client update > Customer portal
Use SKILL: platform-api-contract, client-generation, portal-frontend-core, frontend-debugging
Reason: platform-api-contract protects the schema; client-generation updates types; portal-frontend-core aligns app boundaries; frontend-debugging verifies rendered behavior.
```

```text
Route: Data / Staging mismatch > Seed, RBAC, menu, environment > Internal admin
Use SKILL: staging-data-verifier, systematic-debugging, sql-pro, platform-core
Reason: staging-data-verifier checks live data chains; systematic-debugging keeps the investigation causal; sql-pro improves query evidence; platform-core aligns runtime assumptions.
```

