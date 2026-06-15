---
title: Company Platform Example
description: An anonymized enterprise platform routing example for real-world complexity.
---

This example is based on a company platform with backend services, a customer portal, internal admin tools, documentation, CI/CD, RBAC, and incident workflows.

## Best for

- SaaS platforms
- internal operations systems
- customer portals
- revenue platforms
- teams with live data and deployment gates

## Sample route

```text
Route: Sync / Backend to frontend > API schema and client update > Customer portal
Use SKILL: platform-api-contract, client-generation, portal-frontend-core, frontend-debugging
Reason: platform-api-contract protects the schema; client-generation updates types; portal-frontend-core aligns app boundaries; frontend-debugging verifies rendered behavior.
```

## Why it matters

This route prevents the agent from jumping straight into frontend implementation before the API contract is stable. It also keeps browser verification in scope because generated clients can still fail at runtime.

## Source

- [View `examples/company-platform-sanitized/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/company-platform-sanitized)
- [Open `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/company-platform-sanitized/references/skill-tree.md)
- [Open `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/company-platform-sanitized/references/routing-rules.md)

