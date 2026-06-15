# Routing Rules

## Priority

1. Use GitHub connector skills when PR comments, checks, issues, or remote branch state are the source of truth.
2. Use local code review skills when reasoning about correctness, maintainability, or test gaps.
3. Use CI debugging skills for failing runs and logs.
4. Use git workflow skills for staging, committing, and branch hygiene.

## Conflict Handling

- `github-review-comments` vs `code-review`: use GitHub review comments to fetch and update feedback; use code review to judge whether the feedback is valid.
- `github-ci-debugging` vs `test-runner`: use CI debugging to inspect remote logs; use test runner to reproduce locally.
- `release-checklist` vs `git-workflow`: use release checklist for merge readiness; use git workflow for local commits.
- `devops` vs `github-ci-debugging`: use devops when workflow configuration or runner setup is the likely cause.

## Output Examples

```text
Route: GitHub / PR comments > Address feedback > Remote review
Use SKILL: github-review-comments, code-review, local-editing, test-runner
Reason: github-review-comments fetches unresolved feedback; code-review evaluates it; local-editing applies changes; test-runner verifies behavior.
```

