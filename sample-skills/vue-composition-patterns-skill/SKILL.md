---
name: vue-composition-patterns-skill
description: "Use when designing, refactoring, or reviewing Vue 3 Composition API patterns: composables, watchers, lifecycle effects, shared state, route-aware logic, and browser API wrappers."
metadata:
  domain: frontend
  scope: design, implementation, review
  triggers: Vue 3, Composition API, composable, watcher, lifecycle effect, reactive state, route-aware logic
  exclusions: non-Vue frontend work, browser automation, backend API contract design
  tags: vue, composition-api, frontend, reactivity
---

# Vue Composition Patterns Skill

Use this skill when the core problem is Vue reactivity structure, not general UI styling.

## Workflow

1. Identify state ownership: component-local, composable, store, route, or server state.
2. Keep composables focused on one durable responsibility.
3. Prefer explicit inputs and return values over hidden global state.
4. Keep watchers narrow and name why they exist.
5. Isolate browser APIs behind composables when cleanup or SSR safety matters.
6. Verify behavior in the rendered app when reactivity timing is part of the bug.

## Smells

- A composable that owns unrelated state.
- A watcher that patches around unclear data flow.
- Lifecycle hooks spread across many components for one concern.
- Shared state mutated from too many places.

## Common Supporting Skills

- `vue-expert` for Vue implementation detail.
- `build-web-apps:frontend-testing-debugging` for rendered behavior.
- `browser:control-in-app-browser` for visual verification.
