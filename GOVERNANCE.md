# Governance

Workflow Skill Router uses a maintainer-led governance model while the V2 contributor community grows. The goal is transparent technical decisions and verifiable releases, not decision-making by repository ownership alone.

## Maintainer Responsibilities

Maintainers review contributions, protect security boundaries, keep public claims evidence-backed, preserve the Plugin and SKILL-only installation paths, and apply the V2 release gate. Current maintainers and responsibilities are listed in [MAINTAINERS.md](MAINTAINERS.md).

## Decisions

- Small fixes are decided through pull-request review and passing automated contracts.
- Changes to routing policy, state transitions, MCP schemas, evidence classification, security boundaries, compatibility channels, or release artifacts require a written rationale in the pull request.
- Material architecture changes should update the V2 architecture document or add a decision record before implementation is merged.
- Maintainers seek contributor input in Discussions when a change removes a public capability or creates a migration requirement.

When consensus is not reached, the release maintainer records the decision, alternatives considered, and migration impact. Decisions can be revisited when new implementation evidence is available.

## Release Authority

Only maintainers named with release authority may approve a `v2.*` tag or GitHub release. Automation may build and attest a tagged revision, but it does not decide that the revision is ready. Real model evaluation quota, public evidence promotion, Pages deployment, stable-channel movement, and release publication remain separate approvals.

## Canonical Plugin Distribution Ownership

Plugin runtime, tests, Skill content, generated-target policy, and release
automation are developed only in this canonical repository. The standalone
Plugin repository is an installation target generated from a reviewed canonical
revision; it is not an independent development surface.

Target Scanner, protected-branch, or tag failures fail closed. Maintainers fix
the canonical source or separately authorized live governance prerequisite and
then run a newly authorized release. They do not manually repair target files,
rewrite target history, bypass Scanner, or replace target tags. Installing the
Release GitHub App, applying rulesets, and running a live release remain distinct
privileged external operations.

## Security Authority

Security maintainers coordinate private reports, embargoed fixes, advisories, and disclosure timing. Security-sensitive changes may receive a limited private review before a public patch is available.

## Conflicts of Interest and Conduct

Reviewers must disclose a personal or commercial conflict that could affect a decision and recuse themselves when appropriate. Technical disagreement should be resolved with reproducible evidence and project scope. Conduct concerns may be sent privately to an uninvolved maintainer; when none exists, the release maintainer documents the handling and seeks an independent reviewer where practical.

## Becoming a Maintainer

Maintainer status is based on sustained, high-quality contribution, reliable review, respect for privacy, and demonstrated understanding of V2 contracts. Existing maintainers appoint or remove maintainers through a documented repository change.
