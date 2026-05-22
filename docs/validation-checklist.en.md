# Validation Checklist

Use this checklist before publishing or relying on a workflow skill router.

## Structure

- [ ] `SKILL.md` exists.
- [ ] `SKILL.md` has YAML frontmatter.
- [ ] `name` is hyphen-case.
- [ ] `description` says when to use the skill, not the whole workflow.
- [ ] `references/skill-tree.md` exists.
- [ ] `references/routing-rules.md` exists.
- [ ] Reference files are one level away from `SKILL.md`.

## Routing Quality

- [ ] Every route follows `task nature -> work stage -> technical domain`.
- [ ] Every route chooses 1-4 skills.
- [ ] Each route has one clear primary skill.
- [ ] Supporting skills cover distinct jobs.
- [ ] Broad meta skills are not default choices.
- [ ] Connector tasks prefer connector/plugin skills.

## Conflict Rules

- [ ] Local vs plugin priority is documented.
- [ ] Browser automation choices are documented.
- [ ] Review vs GitHub connector choices are documented.
- [ ] File-format connector choices are documented.
- [ ] User-explicit skill requests are respected.

## Scenario Tests

Test at least these prompts:

```text
Design a new backend API with database schema and test plan.
```

Expected: API, backend, database, QA skills.

```text
Debug a browser-only login failure in a Vue admin app.
```

Expected: frontend debugging, browser, systematic debugging, possibly backend.

```text
Write a technical workflow document with Mermaid diagrams.
```

Expected: documentation, writing, diagram skills.

```text
Address unresolved GitHub PR review comments.
```

Expected: GitHub connector plus review reasoning.

```text
Summarize recent Teams messages and draft a reply.
```

Expected: Teams connector skills.

```text
List files in this folder.
```

Expected: no extra routing.

## Failure Signals

- The router picks more than 4 skills for a single task.
- The router triggers on simple one-line tasks.
- The router selects generic docs skills for file-format tasks that need rendering.
- The router ignores user-named skills.
- The router duplicates equivalent local and plugin skills without a reason.

## Fixes

- Split large routes into smaller work stages.
- Move detailed mappings from `SKILL.md` to `skill-tree.md`.
- Add a conflict rule for repeated mistakes.
- Narrow the frontmatter description if the router triggers too often.
