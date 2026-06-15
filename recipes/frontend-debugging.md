# Recipe: Frontend Debugging

Use this route when a UI bug may involve rendering, state, browser behavior, or API data.

## Good Route

```text
Route: Frontend / Reproduce > Local rendered app > Runtime behavior
Use SKILL: browser, frontend-debugging, systematic-debugging
Reason: browser captures rendered behavior; frontend-debugging maps symptoms to UI code; systematic-debugging keeps the investigation causal.
```

## Browser Choice

- Interactive browser: visual inspection, layout, manual reproduction.
- User Chrome session: existing cookies, login state, extensions, or current tabs.
- Scripted automation: repeatable regression tests after the bug is understood.

## Avoid

- Starting with Playwright before the issue is reproducible.
- Adding visual design skills for a functional rendering bug.
- Treating missing API data as only a frontend state problem.

