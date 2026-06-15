---
title: Frontend Debugging Example
description: Choose between browser inspection, Chrome sessions, Playwright, framework expertise, and API debugging.
---

Frontend bugs often look simple but can cross many boundaries.

## Decision rules

- Use an interactive browser for visual reproduction.
- Use a real Chrome session only when cookies, login state, extensions, or current tabs matter.
- Use Playwright after the issue is understood and needs repeatable regression coverage.
- Use API debugging when data is missing, stale, unauthorized, or malformed.

## Sample route

```text
Route: Frontend / Reproduce > Local rendered app > Runtime behavior
Use SKILL: browser, frontend-debugging, systematic-debugging
Reason: browser captures rendered behavior; frontend-debugging maps symptoms to UI code; systematic-debugging keeps the investigation causal.
```

## Source

See:

```text
examples/frontend-debugging/
```

