# Workflow Skill Router V2

[繁體中文](README.zh-TW.md) · [English](README.en.md) · [Live demo](https://huangchiyu.com/Workflow-skill-router/)

Workflow Skill Router is a runtime-aware routing and orchestration layer for Codex. It turns a request into the smallest verifiable execution envelope, preserves user-selected SKILL boundaries, and keeps long-running Goal work resumable and auditable.

## Why V2 changes the workflow

- **Single** routes one small intent with one minimal Primary capability.
- **Phased** preserves every meaningful stage and reroutes each Phase independently.
- **Managed Goal** maintains a dependency Work Graph, refreshes context on resume, and returns host-safe Goal status candidates.
- **Explicit Skill Lock** applies to small, medium, and Goal work. Recommended support is never read or activated before consent.
- **Runtime Capability Discovery** distinguishes installed metadata from host exposure, authentication, compatibility, policy eligibility, freshness, and risk.
- **Real model evaluation** separates Tier 0 Contract fixtures from fresh Behavior/Outcome attempts.

## Skill-only quickstart

Install [`starter/v2/workflow-skill-router`](starter/v2/workflow-skill-router) as a Codex SKILL. This mode is deliberately reported as `skill-only-fallback`: durable resume, cross-process CAS, full drift detection, and sealed activation instrumentation are not observable. R2/R3 still require host approval.

## Plugin + MCP quickstart

Use the deterministic Plugin archive in [`downloads/`](downloads/) or the source under [`plugins/workflow-skill-router`](plugins/workflow-skill-router). The Plugin exposes exactly ten MCP tools covering runtime sync, planning, next work, route validation, evidence/state, Goal status, model evaluation, comparison, and sanitized export.

```powershell
python plugins/workflow-skill-router/scripts/build-runtime.py --check
cd plugins/workflow-skill-router
npm ci
npm run check
```

`hybrid-full` is claimed only after a verified host handshake and kind-specific bound-content preflight. Plugin installation, SKILL consent, and runtime permission are separate decisions.

## Evaluation evidence boundary

The existing 80 cases are **Tier 0 Contract** fixtures. They prove deterministic compatibility, not real model behavior. Behavior and Outcome require at least three fresh attempts, sealed scoring material, paired manifests, zero hard violations, and a trusted human review verifier. Without an execution adapter the result is `manual-required`; without trusted review it is `review-required` and no public score is emitted.

## Version channels

| Channel | Target | Meaning |
|---|---|---|
| `latest` | V1.3.1 | Stable default until V2 GA |
| `latest-v1` | V1.3.1 | Immutable V1 compatibility asset |
| `latest-v2` | V2 alpha | Skill + Plugin prerelease |

See [V2 architecture](docs/v2-architecture.md), [V1 → V2 upgrade](docs/v1-to-v2-upgrade.md), and the [showcase](docs/showcase.md).

## V1 compatibility resources

The stable V1 surface remains available for existing users: [Blank Router](downloads/workflow-skill-router-blank.zip), [full template](downloads/workflow-skill-router-template.zip), [clean template](downloads/workflow-skill-router-template-clean.zip), the [tutorial catalog](examples/template-skill-catalog), and [`validate-router.py`](scripts/validate-router.py). The original [before/after routing diagram](docs/assets/demo-routing-before-after.svg) is retained for public-readiness compatibility.

## Validation

```powershell
$env:PYTHONPATH = "packages/router-core/src"
python -m unittest discover -s packages/router-core/tests -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
python scripts/build-v2-demo-data.py --check
python scripts/build-release-artifacts.py --check
```

MIT licensed. No telemetry is enabled by default.
