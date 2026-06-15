---
name: frontend-debugging-workflow
description: Use when investigating rendered frontend bugs, browser-only failures, broken interactions, visual regressions, hydration issues, or UI behavior that needs browser reproduction and regression coverage.
metadata:
  domain: frontend
  scope: debugging, verification
  triggers: browser-only bug, rendered UI failure, broken interaction, visual regression, hydration issue, frontend regression
  exclusions: pure backend failure, database migration, documentation-only edit
  tags: frontend, debugging, browser, regression
---

# Frontend Debugging Workflow

Use this skill when the failure is visible or interactive in a browser.

## Workflow

1. Reproduce the symptom in the browser.
2. Record the URL, viewport, user action, expected behavior, and actual behavior.
3. Check console, network, DOM state, and application state.
4. Trace the symptom back to source code.
5. Fix the smallest cause.
6. Add a regression check with Playwright or the repo's test framework when useful.
7. Re-run browser verification.

## Browser vs Playwright

- Use browser inspection first when the issue is not understood.
- Use Playwright after the scenario is stable enough to automate.
- Use existing Chrome state only when login, cookies, extensions, or current tabs matter.

## Common Supporting Skills

- `browser:control-in-app-browser` for local visual reproduction.
- `playwright` for scripted regression.
- `systematic-debugging` for causal investigation.
