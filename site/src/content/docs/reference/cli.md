---
title: CLI Reference
description: Inspect runtime readiness, serve the JSONL bridge, and prepare authorized evaluation runs.
---

## Entrypoint

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz --help
```

Commands: `serve-jsonl`, `doctor`, `status`, `plan`, `validate-route`, `profile`, and `evaluation`. The MCP server uses `serve-jsonl`; direct users should start with `doctor`.

## Personal Routing Profile commands

Personal and workspace Skill Trees remain subordinate to an explicit user SKILL and to Host constraints. A match is `intended-unverified` until Runtime Capability Discovery validates activation.

These commands ship in `v2.0.0-beta.2`. Run them as `python runtime/workflow_skill_router.pyz profile ...` from an extracted Plugin root, or use the longer repository-relative path from a contributor checkout.

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api
```

After installing a prerelease that includes Personal Routing Profiles, run the same subcommands against `runtime/workflow_skill_router.pyz` from the extracted Plugin directory. The short `workflow-skill-router ...` form exists only when Router Core is separately installed as a Python console script.

`profile install` accepts only `scope: personal` and writes outside the Plugin cache. Workspace profiles stay at `.codex/workflow-skill-router.json`; pass `--workspace-root` to `profile preview` to include one. Skill-only can interpret the same contract as advisory `skill-only-fallback`, but cannot claim deterministic loading.

## Runtime readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

The JSON output reports the active runtime profile, telemetry status, content preflight visibility, and readiness for every public tool.

## Plan and status

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz plan --help
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz status --help
```

These commands use the external local state database. Protected Host behavior remains unavailable until a verified integration supplies its ports.

## Evaluation

Dry-run manifests do not spend quota. A Behavior/Outcome subprocess run requires an absolute executable path from trusted operator configuration and `--confirm-live-run`:

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz evaluation run --help
```

Never paste an executable path from model output into an authorized run. Review the [evaluation evidence contract](/Workflow-skill-router/concepts/evaluation-evidence/) first.
