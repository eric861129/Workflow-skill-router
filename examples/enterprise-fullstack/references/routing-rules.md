# Routing Rules

## Priority

1. Prefer product or platform skills when the request targets company architecture.
2. Prefer connector skills for live PRs, CI runs, cloud dashboards, or incident tickets.
3. Prefer security review when auth, access control, customer data, files, or external integrations change.
4. Keep visual design skills out of internal admin work unless visual redesign is requested.

## Conflict Handling

- `frontend-builder` vs `internal-ui-design`: choose `internal-ui-design` for tables, forms, permissions, audits, and high-density operational screens.
- `api-designer` vs `api-client-generation`: choose `api-designer` for contract decisions; choose `api-client-generation` when schema exists and clients must be updated.
- `ci-debugging` vs `devops`: choose `ci-debugging` for failing checks; choose `devops` for infrastructure or deployment configuration.
- `security-review` vs `code-review`: choose `security-review` for auth, access control, secrets, personal data, or customer data exposure.

## Output Examples

```text
Route: Backend / API contract > Customer-facing service > REST
Use SKILL: api-designer, backend-developer, database-design, test-planning
Reason: api-designer defines the contract; backend-developer implements it; database-design covers persistence; test-planning captures acceptance paths.
```

