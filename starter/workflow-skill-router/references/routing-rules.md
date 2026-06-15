# Routing Rules

## Placeholder Policy

The route examples in this starter use placeholder skill names. Replace names such as `backend-developer`, `browser`, `test-planning`, and `github-connector` with the exact skill names your agent can actually load.

For a public-safe catalog with concrete skill names, compare this starter with `examples/template-skill-catalog/references/routing-rules.md`.

## Priority

1. Respect explicit user requests. If the user names a skill or plugin, include it unless unavailable.
2. Prefer connector/plugin skills when external systems are the core task.
3. Prefer local custom skills for repository work and implementation judgment.
4. Prefer system skills for platform-specific tasks such as skill creation, plugin installation, or product documentation.
5. Use broad meta workflow skills only when their workflow is explicitly requested or clearly required.

## Skill Count

- Use one Primary skill for narrow tasks.
- Use two to four skills for cross-domain work.
- If more than four skills seem useful, split the work into stages.
- Do not include two skills that do the same job unless one is a connector and one is a reasoning/review skill.

## Evaluation Flow

- Keep route examples small enough to turn into scenarios.
- Record one expected Primary skill and only distinct Supporting skills.
- Add forbidden skills when a related domain should stay inactive.
- Use `max_skills` to enforce the smallest useful route size.
- Re-run `scripts/evaluate-routing.py` after changing this file or the skill tree.

## Conflict Handling

- Local skill vs connector skill: choose the connector when live external state is the source of truth; choose the local skill when implementing or reasoning over repository code.
- Browser vs scripted automation: choose an interactive browser skill for visual inspection and session-dependent behavior; choose a scripted browser skill for repeatable regression checks.
- Review skill vs GitHub connector: use the connector to fetch or update PR comments; use the review skill to reason about the feedback.
- File-format skill vs generic docs skill: choose the file-format skill when rendering, layout, comments, or fidelity matters.
- Meta workflow vs narrow skill: choose the narrow skill by default; use the meta workflow only when the workflow itself is the task.

## Output Examples

Backend API:

```text
Route: Architecture / API / Backend > API contract design > REST service
Use SKILL: api-designer, backend-developer, database-design, test-planning
Reason: api-designer defines the contract; backend-developer handles implementation; database-design covers persistence; test-planning covers acceptance cases.
```

Frontend debug:

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: frontend-debugging, browser, systematic-debugging
Reason: frontend-debugging handles rendered UI failures; browser reproduces the issue; systematic-debugging keeps the investigation causal.
```

Simple command:

```text
No extra routing needed: this is a single-step command.
```

## Safety Defaults

- Inspect the existing project before deciding implementation details.
- Keep route outputs small and explainable.
- Do not simulate live connector data.
- Do not expose private repository names, paths, secrets, customer names, or deployment details in public examples.
