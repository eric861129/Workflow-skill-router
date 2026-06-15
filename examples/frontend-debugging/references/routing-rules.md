# Routing Rules

## Priority

1. Use `browser` first when the bug is visual, interactive, or layout-dependent.
2. Use `chrome-session` only when existing cookies, extensions, or user login state matter.
3. Use `playwright` when the goal is repeatable automation or regression coverage.
4. Use framework expertise when the likely cause is component state, routing, lifecycle, or reactivity.

## Conflict Handling

- `browser` vs `playwright`: choose `browser` for discovery and visual inspection; choose `playwright` for repeatable verification.
- `chrome-session` vs `browser`: choose `chrome-session` only for real user session state; otherwise choose `browser`.
- `ui-debugging` vs `framework-expert`: choose `ui-debugging` for layout/CSS; choose `framework-expert` for component behavior and state.
- `api-debugging` vs `frontend-debugging`: choose `api-debugging` when data is missing, stale, unauthorized, or malformed.

## Output Examples

```text
Route: Frontend / Reproduce > Local rendered app > Runtime behavior
Use SKILL: browser, frontend-debugging, systematic-debugging
Reason: browser captures real rendered behavior; frontend-debugging maps symptoms to UI code; systematic-debugging keeps the investigation causal.
```

