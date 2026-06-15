# Common Engineering Routing Rules

## Skill Count

- Use exactly one Primary skill.
- Use up to three Supporting skills.
- Split the work into phases when more than four skills seem useful.
- Do not include skills that do the same job unless one provides live external state and the other provides local reasoning.

## Priority

1. Respect explicitly requested skills.
2. Prefer connector or plugin skills when live external state is the source of truth.
3. Prefer local engineering skills for repository design, implementation, and durable judgment.
4. Prefer narrow workflow skills over broad meta skills unless the process itself is the task.

## Common Conflicts

- Browser vs Playwright: use `browser:control-in-app-browser` for visual reproduction and `playwright` for repeatable scripted regression.
- Chrome vs Browser: use `chrome:control-chrome` only when existing Chrome login state, cookies, extensions, or current tabs matter.
- REST design vs OpenAPI generation: use `api-designer` for resource semantics; use `openapi-contract-generation-skill` for schema lifecycle and generated clients.
- API governance vs implementation: use `api-guidelines-skill` for naming, compatibility, pagination, versioning, and error semantics; use backend implementation skills after the contract is clear.
- Vue expert vs composition patterns: use `vue-expert` for general Vue work; use `vue-composition-patterns-skill` when composables, watchers, shared state, or reactivity boundaries are the core problem.
- Security review vs normal code review: use `codex-security:security-diff-scan` for auth, RBAC, secrets, data exposure, or deployment-sensitive diffs; use `receiving-code-review` for general maintainability feedback.
- File-format connectors vs docs prose: use `documents:documents`, `spreadsheets:Spreadsheets`, `presentations:Presentations`, or `pdf` when the rendered artifact matters.

## Output Examples

```text
Route: API / OpenAPI lifecycle > Schema diff and client generation > Frontend sync
Use SKILL: openapi-contract-generation-skill, openapi-to-typescript, api-designer, build-web-apps:frontend-testing-debugging
Reason: openapi-contract-generation-skill manages schema lifecycle; openapi-to-typescript updates types; api-designer checks contract semantics; frontend-testing-debugging verifies runtime behavior.
```

```text
Route: Frontend / Debug > Browser reproduction > Internal admin
Use SKILL: build-web-apps:frontend-testing-debugging, browser:control-in-app-browser, playwright, systematic-debugging
Reason: frontend-testing-debugging maps UI symptoms to code; browser reproduces rendered behavior; playwright captures the regression; systematic-debugging keeps the investigation causal.
```

```text
Route: Security / PR diff > Auth and data exposure > Review
Use SKILL: codex-security:security-diff-scan, receiving-code-review, systematic-debugging, github:github
Reason: security-diff-scan finds security risks; receiving-code-review evaluates maintainability feedback; systematic-debugging verifies root cause; github fetches PR state.
```
