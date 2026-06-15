# Recipe: PR And CI Review

Use this route when GitHub remote state is part of the task.

## Good Route

```text
Route: GitHub / PR comments > Address feedback > Remote review
Use SKILL: github-review-comments, code-review, local-editing, test-runner
Reason: github-review-comments fetches unresolved feedback; code-review evaluates it; local-editing applies changes; test-runner verifies behavior.
```

## CI Failure Route

```text
Route: CI / Failed run > Build or test failure > GitHub Actions
Use SKILL: github-ci-debugging, github-connector, test-runner, devops
Reason: github-ci-debugging reads logs; github-connector checks run state; test-runner reproduces locally; devops covers workflow configuration.
```

## Avoid

- Using local review skills when the missing data is in GitHub.
- Editing CI config before reading the failing run.
- Combining release readiness and code review into one route when either can be handled separately.

