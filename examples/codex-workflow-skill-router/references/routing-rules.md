# Routing Rules

## Priority

1. Respect explicit user requests. If the user names a SKILL or plugin, include it unless unavailable.
2. Prefer connector/plugin SKILLs when external systems are the core task.
3. Prefer local custom SKILLs for broad engineering judgment and repository work.
4. Prefer system SKILLs for OpenAI docs, image generation, plugin creation, skill creation, and skill installation.
5. Use broad Superpowers meta SKILLs only when the workflow is explicitly requested or clearly required.

## Skill Count

- Use one Primary SKILL for narrow tasks.
- Use two to four SKILLs for cross-domain work.
- If more than four seem useful, split the workflow into stages.
- Do not include two SKILLs that do the same job unless one is a connector and one is a reasoning or review skill.

## Conflict Handling

- `systematic-debugging` vs `superpowers:systematic-debugging`: use local `systematic-debugging` by default; use the Superpowers version when following that workflow.
- `executing-plans` vs `superpowers:executing-plans`: use local `executing-plans` for normal plan execution; use the Superpowers version when explicitly requested.
- `receiving-code-review` vs `github:gh-address-comments`: use GitHub skill to fetch or resolve PR comments; use receiving-code-review to reason about whether comments are valid.
- `frontend-design` vs `build-web-apps:frontend-app-builder`: use frontend-app-builder for full new frontend apps; use frontend-design for targeted visual and interaction design.
- `playwright` vs `browser:control-in-app-browser`: use browser for Codex in-app browser and local visual verification; use Playwright for scripted browser automation.
- `documents`, `spreadsheets`, `presentations`, `pdf`: choose by file type when rendering or file fidelity matters.

## Output Examples

```text
Route: Architecture / API / Backend > API contract design > C#/.NET
Use SKILL: api-designer, csharp-developer, database-schema-designer, qa-test-planner
Reason: api-designer defines the contract; csharp-developer handles .NET implementation; database-schema-designer covers data modeling; qa-test-planner covers acceptance tests.
```

```text
No extra routing needed: this is a single-step shell query.
```
