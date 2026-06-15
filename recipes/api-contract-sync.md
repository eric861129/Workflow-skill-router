# Recipe: API Contract Sync

Use this route when backend API contracts and frontend clients must move together.

## Good Route

```text
Route: Sync / Backend to frontend > API schema and client update > Customer portal
Use SKILL: api-contract, client-generation, frontend-core, frontend-debugging
Reason: api-contract protects the schema; client-generation updates types; frontend-core aligns app boundaries; frontend-debugging verifies rendered behavior.
```

## Avoid

- Adding a database skill unless schema or migration work is actually required.
- Starting with frontend implementation before the API contract is stable.
- Skipping verification in the rendered app.

## Useful Conflict Rule

Use API contract skills for endpoint shape, DTOs, errors, and generated schema. Use client generation skills only after the contract source is known.

