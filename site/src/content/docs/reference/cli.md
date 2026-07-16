---
title: CLI Reference
description: Inspect runtime readiness, serve the JSONL bridge, and prepare authorized evaluation runs.
---

## Entrypoint

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz --help
```

Commands: `serve-jsonl`, `doctor`, `status`, `plan`, `validate-route`, and `evaluation`. The MCP server uses `serve-jsonl`; direct users should start with `doctor`.

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
