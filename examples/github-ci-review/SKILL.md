---
name: github-ci-review-router
description: Route GitHub-centered work across PR review comments, CI failures, branch readiness, release checks, code review reasoning, and local git hygiene.
---

# GitHub CI Review Router

Use this router when GitHub remote state matters and the agent must decide between connector work, local review, CI diagnosis, or release readiness.

## Workflow

1. Decide whether the source of truth is GitHub remote state, local code, CI logs, or release criteria.
2. Select one Primary skill and up to three Supporting skills.
3. Explain the route before fetching, reviewing, fixing, or publishing.

