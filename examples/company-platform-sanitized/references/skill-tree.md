# Workflow Skill Tree

## Platform / Entry / Scope

- Platform / Intake / Task boundary and risk: Primary: `platform-core`; Supporting: `requirements-clarity`, `architecture-designer`
- Platform / Architecture / Service and app boundaries: Primary: `platform-architecture`; Supporting: `platform-core`, `architecture-designer`, `backend-developer`

## Backend / API / Contracts

- Backend / API contract / Controller, DTO, envelope, OpenAPI: Primary: `platform-api-contract`; Supporting: `platform-core`, `api-designer`, `client-generation`
- Backend / Implementation / Clean service code: Primary: `platform-clean-code`; Supporting: `platform-core`, `platform-architecture`, `backend-developer`
- Backend / Data boundary / Legacy data isolation: Primary: `platform-architecture`; Supporting: `database-design`, `api-designer`

## Frontend / Customer Portal / Internal Admin

- Frontend / Customer portal / Public user workflow: Primary: `portal-frontend-core`; Supporting: `frontend-builder`, `ui-design`, `browser`
- Frontend / Internal admin / Operational forms and tables: Primary: `internal-admin-ui`; Supporting: `frontend-builder`, `browser`, `accessibility-review`
- Frontend / Monorepo mechanics / Workspace, env, proxy, shared packages: Primary: `frontend-monorepo`; Supporting: `portal-frontend-core`, `framework-expert`, `frontend-debugging`

## Sync / Legacy / Data

- Sync / Backend to frontend / API schema and client update: Primary: `platform-api-contract`; Supporting: `client-generation`, `portal-frontend-core`, `frontend-debugging`
- Legacy / Migration / Old workflow to platform service and portal: Primary: `legacy-migration`; Supporting: `spec-miner`, `platform-core`, `portal-frontend-core`
- Data / Staging mismatch / Seed, RBAC, menu, environment: Primary: `staging-data-verifier`; Supporting: `systematic-debugging`, `sql-pro`, `platform-core`

## Security / Incident / Release

- Security / Sensitive change / Auth, RBAC, customer data, public links: Primary: `platform-security`; Supporting: `security-diff-scan`, `platform-api-contract`, `staging-data-verifier`
- Incident / Stabilization / Production or staging outage: Primary: `incident-response`; Supporting: `deployment-governance`, `systematic-debugging`, `github-connector`
- Release / Readiness / Build, test, browser QA, commit: Primary: `platform-release-checklist`; Supporting: `platform-core`, `frontend-debugging`, `git-workflow`
- Deployment / Promotion / CI, artifacts, rollback, approval: Primary: `deployment-governance`; Supporting: `github-connector`, `devops`, `platform-release-checklist`

## Documentation / Analytics / Collaboration

- Documentation / Platform docs / Source docs and generated references: Primary: `docs-workflow`; Supporting: `documentation-writer`, `code-documentation`, `diagramming`
- Analytics / Operations dashboard / KPI definitions and diagnosis: Primary: `analytics-reporting`; Supporting: `dashboard-builder`, `spreadsheet-tool`
- Collaboration / Workspace files / Docs, sheets, and review comments: Primary: `workspace-connector`; Supporting: `document-tool`, `spreadsheet-tool`

