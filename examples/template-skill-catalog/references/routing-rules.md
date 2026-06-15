# Routing Rules

## Output Contract

Complex tasks:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

Simple tasks:

```text
No extra routing needed: reason
```

## Selection Rules

- Select one Primary skill and at most three Supporting skills.
- Use the smallest useful skill set; do not add related skills unless they change the execution.
- Prefer implementation skills for code changes, planning skills for unclear work, and verification skills for test or QA work.
- Use `playwright` for repeatable browser checks and `systematic-debugging` for causal investigation.
- Use `code-documenter`, `mermaid-diagrams`, and `c4-architecture` when the deliverable is documentation or diagrams.
- Use `commit-work`, `finishing-a-development-branch`, and `session-handoff` near the end of a branch, not at the beginning of every task.
- Keep organization-specific deployment, repository, and access rules outside this public catalog.

## Conflict Rules

- `requirements-clarity` vs `executing-plans`: choose `requirements-clarity` when the request is still ambiguous; choose `executing-plans` when the plan is already accepted.
- `api-designer` vs `api-guidelines-skill`: choose `api-designer` for endpoint and schema design; choose `api-guidelines-skill` for governance, naming, pagination, versioning, and error semantics.
- `database-schema-designer` vs `database-optimizer`: choose schema design for model and migration work; choose optimization for slow queries and runtime performance.
- `frontend-design` vs `vue-expert`: choose `frontend-design` for product UI and interaction quality; choose `vue-expert` for Vue component implementation.
- `design-system-starter` vs `storybook-design-system-skill`: choose `design-system-starter` for system setup and token architecture; choose `storybook-design-system-skill` for component states and review workflows.
- `code-documenter` vs `doc-coauthoring`: choose `code-documenter` for technical docs; choose `doc-coauthoring` when the user wants a collaborative writing flow.
