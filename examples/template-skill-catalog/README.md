# Template Skill Catalog

This example mirrors the public-safe skill set available in `downloads/workflow-skill-router-template.zip`.

Use it when you want to inspect how a real downloadable skill pack can be grouped into practical routing categories without exposing organization-specific rules.

## Intended Audience

- Developers trying Workflow Skill Router for the first time.
- Teams that want a public-safe reference before building their own private overlay.
- Maintainers who want to publish a skill catalog with clear route examples.

## Sample Prompts

```text
Design the API contract and database boundary for a new customer profile workflow.
```

```text
Debug a Vue reactivity issue and add a Playwright regression check.
```

```text
Turn an architecture discussion into a C4 diagram and implementation handoff.
```

## Complete Case Studies

See [`references/sample-routes.md`](references/sample-routes.md) for copyable examples in this format:

```text
User prompt -> Route -> Use SKILL -> Reason
```

The case studies cover API contract sync, database migration risk, Vue browser regressions, PR and CI repair, architecture handoff, and dependency upgrade release readiness.

## Source Files

- `SKILL.md`
- `references/skill-tree.md`
- `references/routing-rules.md`
- `references/sample-routes.md`
