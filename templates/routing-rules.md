# Routing Rules

## Priority

1. Respect explicit user requests. If the user names a skill or plugin, include it unless unavailable.
2. Prefer connector/plugin skills when external systems are the core task.
3. Prefer local custom skills for repository work and implementation judgment.
4. Prefer system skills for platform-specific tasks.
5. Use broad meta skills only when the workflow is explicitly requested or clearly required.

## Skill Count

- Use one Primary skill for narrow tasks.
- Use two to four skills for cross-domain work.
- If more than four seem useful, split the workflow into stages.
- Do not include two skills that do the same job unless one is a connector and one is a local reasoning or review skill.

## Conflict Handling

- Connector vs local reasoning: choose the connector when live external state is the source of truth; choose local reasoning when implementing or reviewing repository code.
- Browser vs scripted automation: use browser for visual reproduction and inspection; use scripted automation for repeatable regression checks.
- Review comments vs code review: use a connector to fetch or update comments; use a review skill to reason about validity and implementation risk.
- File formats vs generic docs: choose file-format skills when rendering, comments, layout, or fidelity matters.
- Meta workflow vs narrow task skill: choose the narrow skill by default; use the meta workflow only when the workflow is the task.

## Output Examples

```text
Route: Architecture / API / Backend > API contract design > REST service
Use SKILL: api-designer, backend-developer, database-design, test-planning
Reason: api-designer defines the contract; backend-developer handles implementation; database-design covers persistence; test-planning covers acceptance cases.
```

```text
No extra routing needed: this is a single-step command.
```
