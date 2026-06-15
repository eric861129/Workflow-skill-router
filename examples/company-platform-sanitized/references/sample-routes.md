# Company Platform Sample Routes

Use these examples as a public-safe company platform catalog. Skill names are anonymized placeholders so teams can map them to their own private or public skills.

## Route Catalog

```text
Route: Platform / Intake > Task boundary and risk > Cross-app change
Use SKILL: platform-core, requirements-clarity, architecture-designer
Reason: platform-core anchors platform context; requirements-clarity narrows scope; architecture-designer checks the cross-app risk.
```

```text
Route: Platform / Architecture > Service and app boundaries > Modular platform
Use SKILL: platform-architecture, platform-core, architecture-designer, backend-developer
Reason: platform-architecture owns boundaries; platform-core aligns conventions; architecture-designer frames tradeoffs; backend-developer checks implementation fit.
```

```text
Route: Backend / API contract > Controller, DTO, envelope, OpenAPI > Partner-facing endpoint
Use SKILL: platform-api-contract, platform-core, api-designer, client-generation
Reason: platform-api-contract protects schema rules; platform-core keeps platform conventions; api-designer checks resource semantics; client-generation updates consumers.
```

```text
Route: Backend / Implementation > Clean service code > Business workflow
Use SKILL: platform-clean-code, platform-core, platform-architecture, backend-developer
Reason: platform-clean-code drives maintainable implementation; platform-core applies conventions; platform-architecture guards boundaries; backend-developer handles code shape.
```

```text
Route: Frontend / Customer portal > Public user workflow > Account self-service
Use SKILL: portal-frontend-core, frontend-builder, ui-design, browser
Reason: portal-frontend-core aligns app boundaries; frontend-builder implements UI; ui-design improves flow quality; browser verifies the rendered journey.
```

```text
Route: Frontend / Internal admin > Operational forms and tables > Support workflow
Use SKILL: internal-admin-ui, frontend-builder, browser, accessibility-review
Reason: internal-admin-ui fits operational density; frontend-builder implements forms; browser checks behavior; accessibility-review catches usability gaps.
```

```text
Route: Frontend / Monorepo mechanics > Workspace, env, proxy, shared packages > Multi-app platform
Use SKILL: frontend-monorepo, portal-frontend-core, framework-expert, frontend-debugging
Reason: frontend-monorepo owns workspace mechanics; portal-frontend-core keeps app boundaries; framework-expert handles framework behavior; frontend-debugging verifies runtime issues.
```

```text
Route: Sync / Backend to frontend > API schema and client update > Customer portal
Use SKILL: platform-api-contract, client-generation, portal-frontend-core, frontend-debugging
Reason: platform-api-contract protects the schema; client-generation updates types; portal-frontend-core aligns app boundaries; frontend-debugging verifies rendered behavior.
```

```text
Route: Legacy / Migration > Old workflow to platform service and portal > Operational replacement
Use SKILL: legacy-migration, spec-miner, platform-core, portal-frontend-core
Reason: legacy-migration maps old behavior; spec-miner extracts facts; platform-core aligns service design; portal-frontend-core handles the new user surface.
```

```text
Route: Data / Staging mismatch > Seed, RBAC, menu, environment > Internal admin
Use SKILL: staging-data-verifier, systematic-debugging, sql-pro, platform-core
Reason: staging-data-verifier checks live data chains; systematic-debugging keeps the investigation causal; sql-pro improves query evidence; platform-core aligns runtime assumptions.
```

```text
Route: Security / Sensitive change > Auth, RBAC, customer data, public links > Review
Use SKILL: platform-security, security-diff-scan, platform-api-contract, staging-data-verifier
Reason: platform-security applies the platform risk model; security-diff-scan reviews changed code; platform-api-contract checks API exposure; staging-data-verifier validates access behavior.
```

```text
Route: Incident / Stabilization > Production or staging outage > Restore service
Use SKILL: incident-response, deployment-governance, systematic-debugging, github-connector
Reason: incident-response coordinates stabilization; deployment-governance checks rollback options; systematic-debugging finds cause; github-connector gathers PR and run evidence.
```

```text
Route: Release / Readiness > Build, test, browser QA, commit > Operations dashboard
Use SKILL: platform-release-checklist, platform-core, frontend-debugging, git-workflow
Reason: platform-release-checklist confirms readiness; platform-core checks platform assumptions; frontend-debugging verifies UI; git-workflow keeps the release commit clean.
```

```text
Route: Deployment / Promotion > CI, artifacts, rollback, approval > Controlled release
Use SKILL: deployment-governance, github-connector, devops, platform-release-checklist
Reason: deployment-governance owns promotion policy; github-connector reads run state; devops checks infrastructure; platform-release-checklist confirms release quality.
```

```text
Route: Documentation and analytics > Platform docs, KPI dashboard, workspace files > Leadership update
Use SKILL: docs-workflow, analytics-reporting, workspace-connector, diagramming
Reason: docs-workflow keeps durable docs; analytics-reporting explains metrics; workspace-connector handles shared files; diagramming clarifies workflow and data flow.
```
