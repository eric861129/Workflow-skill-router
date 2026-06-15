---
title: Common Engineering Routes
description: A larger routing example built from common real-world software engineering workflows.
---

This example shows how a mature multi-skill agent can route common engineering work without loading every related skill at once.

## Best for

- backend, API, OpenAPI, and database work
- frontend, Vue, browser, Playwright, and design-system work
- docs, review, CI, DevOps, security, analytics, and connectors
- readers who want concrete skill names instead of abstract placeholders

## Sample route

```text
Route: API / OpenAPI lifecycle > Schema diff and client generation > Frontend sync
Use SKILL: openapi-contract-generation-skill, openapi-to-typescript, api-designer, build-web-apps:frontend-testing-debugging
Reason: openapi-contract-generation-skill manages schema lifecycle; openapi-to-typescript updates types; api-designer checks contract semantics; frontend-testing-debugging verifies runtime behavior.
```

## Source

- [View `examples/common-engineering-routing/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/common-engineering-routing)
- [Open `references/skill-tree.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/skill-tree.md)
- [Open `references/routing-rules.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/examples/common-engineering-routing/references/routing-rules.md)

For copyable skill implementations, see:

- [View `sample-skills/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)
