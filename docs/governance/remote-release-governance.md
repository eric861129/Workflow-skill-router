# Remote Release Governance

This guide defines the live GitHub configuration that protects V2 releases for
`eric861129/Workflow-skill-router`. The checked-in contract is
`.github/branch-protection.json`; live configuration must be applied by an
authorized maintainer and then verified without mutations.

## Required target state

The protected branch is `main`. It requires pull requests and resolved review
conversations. Force pushes and branch deletion are blocked.

Required status checks are strict (the branch must be up to date) and must use
these Check Run display names from GitHub Actions Integration (`app_id` `15368`):

- `Core, documentation, and policy contracts`
- `Site visual regression`
- `Required cross-platform V2 gate`

An active ruleset named `Immutable V2 release tags` targets `refs/tags/v2.*`.
It blocks tag creation, update, and deletion. Its only required bypass actor is
the dedicated Workflow Skill Router Release GitHub App (`actor_id` `4361147`,
type `Integration`, mode `always`). The `Release V2` workflow mints a scoped
Contents-write installation token only after source and preflight gates pass.
That allows the workflow to create or verify its immutable release tag while
preventing manual tag changes and preventing the default GitHub Actions token
from acting as a tag bypass.

## Apply through the GitHub UI

Applying these settings is privileged external work. It changes remote GitHub
configuration and must be performed only by a maintainer with the necessary
repository administration authority.

1. Open the repository **Settings** and configure branch protection for `main`.
   Require pull requests, require resolved conversations, enable the three exact
   check-run names above with strict status checks, and keep force pushes and
   deletions disabled.
2. Open **Rules** and create or update the active `Immutable V2 release tags`
   ruleset. Target `refs/tags/v2.*`, block creation, update, and deletion, and
   grant the `always` bypass only to Workflow Skill Router Release GitHub App
   `4361147`.
3. Re-check that no additional bypass actor can create, update, or delete V2
   tags. Record the authorized change under the applicable repository process.

## Apply through the GitHub API

API application is also privileged external work. Use an approved credential
with repository-administration authority and an explicit reviewed request body
that reproduces `.github/branch-protection.json`. Do not use an ad-hoc command
that silently applies, loosens, or replaces settings.

Before submitting an API change, compare the intended branch-protection and
ruleset payloads against the checked-in contract. After GitHub reports success,
use the verifier below; a successful HTTP response alone is not sufficient
evidence that the live configuration matches the contract.

## Read-only verification boundary

Run this command before the release dispatch:

```powershell
python scripts/verify-remote-governance.py --repo eric861129/Workflow-skill-router
```

The verifier is read-only: it does not change GitHub configuration. A pass
confirms the captured configuration meets the checked-in contract. It does not
prove that a release workflow has successfully exercised the Release GitHub App
bypass; that is a separate live release-workflow concern. A failure means the
remote settings have not been proven and must block the release checklist.
