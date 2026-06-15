# Workflow Skill Tree

## Pull Request / Review

- GitHub / PR comments / Address feedback: Primary: `github-review-comments`; Supporting: `code-review`, `local-editing`, `test-runner`
- GitHub / PR summary / Reviewer context: Primary: `github-connector`; Supporting: `code-review`, `documentation-writer`
- Review / Local diff / Maintainability or risk: Primary: `code-review`; Supporting: `test-planning`, `security-review`

## CI / Checks

- CI / Failed GitHub Actions / Test or build failure: Primary: `github-ci-debugging`; Supporting: `github-connector`, `test-runner`, `devops`
- CI / Flaky failure / Evidence gathering: Primary: `github-ci-debugging`; Supporting: `systematic-debugging`, `test-runner`
- CI / Config change / Workflow or runner: Primary: `devops`; Supporting: `github-ci-debugging`, `github-connector`

## Release / Git

- Release / Merge readiness / Protected branch: Primary: `release-checklist`; Supporting: `github-connector`, `github-ci-debugging`, `code-review`
- Git / Commit hygiene / Local changes: Primary: `git-workflow`; Supporting: `code-review`, `test-runner`

