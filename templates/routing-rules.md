# Routing Rules

## Priority

1. Respect explicit user requests. If the user names a SKILL or plugin, include it unless it is unavailable.
2. Prefer connector/plugin SKILLs when external systems are the core task.
3. Prefer local custom SKILLs for broad engineering judgment and repository work.
4. Prefer system SKILLs for platform-specific tasks.
5. Use broad meta SKILLs only when the workflow is explicitly requested or clearly required.

## Skill Count

- Use one primary SKILL for narrow tasks.
- Use two to four SKILLs for cross-domain work.
- If more than four seem useful, split the workflow into stages.
- Do not include two skills that do the same job unless one is a connector and one is a local reasoning/review skill.

## Conflict Handling

- Debugging: choose the local/systematic debugging skill by default; use a meta workflow only when requested.
- Execution plans: use the normal plan execution skill by default; use a meta workflow for explicit methodology-driven work.
- Review comments: use a connector skill to fetch or update PR comments; use a review skill to reason about the feedback.
- Browser work: use an interactive browser skill for visual verification; use Playwright or equivalent for scripted automation.
- File formats: choose document/spreadsheet/presentation/PDF skills when rendering or file fidelity matters.

## Output Examples

```text
Route: Architecture/API/Backend > API contract design > C#/.NET
Use SKILL: api-designer, csharp-developer, database-schema-designer, qa-test-planner
Reason: api-designer defines the contract; csharp-developer handles backend implementation; database-schema-designer handles data modeling; qa-test-planner covers acceptance tests.
```

```text
No extra routing needed: this is a single-step command.
```
