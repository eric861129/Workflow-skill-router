# Routing Rules

## Priority

1. Honor explicit user-requested skills.
2. Prefer connector skills for live external state.
3. Prefer local engineering skills for code changes.
4. Use meta workflow skills only when the process is the task.

## Conflict Handling

- `browser` vs `test-runner`: use `browser` for visual reproduction; use `test-runner` for repeatable checks.
- `documentation-writer` vs `code-review`: use documentation for reader-facing content; use review for risk and correctness.
- `github-connector` vs `git-workflow`: use GitHub for remote PRs/issues/checks; use git workflow for local branch and commit hygiene.

## Output Examples

```text
Route: Backend / API > Contract design > REST service
Use SKILL: api-designer, backend-developer, test-planning
Reason: api-designer defines the contract; backend-developer maps it to code; test-planning captures acceptance cases.
```

