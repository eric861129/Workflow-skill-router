---
name: api-guidelines-skill
description: "Use when designing or reviewing REST API governance: resource naming, pagination, filtering, versioning, compatibility, error semantics, idempotency, and contract consistency."
---

# API Guidelines Skill

Use this skill before implementation when the API shape is still negotiable, and during review when an endpoint may break consistency.

## Workflow

1. Identify the resource, actor, and state transition.
2. Check method semantics, idempotency, and status codes.
3. Define request, response, pagination, filtering, and sorting behavior.
4. Define error shape and compatibility constraints.
5. Recommend OpenAPI updates only after the route semantics are stable.

## Review Checklist

- Resource names are nouns and stable over time.
- HTTP methods match intent.
- Pagination and filtering are explicit.
- Error responses use one envelope shape.
- Backward compatibility risks are named.
- Authorization-sensitive fields are not leaked by default.

## Common Supporting Skills

- `api-designer` for broader REST or GraphQL design.
- `openapi-contract-generation-skill` for schema lifecycle and generated clients.
- `code-documenter` for developer-facing API docs.
