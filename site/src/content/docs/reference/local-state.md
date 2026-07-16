---
title: Local State
description: Understand where Router state lives, what it contains, and how upgrades affect it.
---

## Default locations

| Platform | State root |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Codex\workflow-skill-router` |
| macOS | `~/Library/Application Support/Codex/workflow-skill-router` |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` |

Set `WORKFLOW_SKILL_ROUTER_DATA_DIR` to use another directory. The runtime rejects a state path inside the Plugin installation/cache boundary.

## Stored data

Bundled local R0 stores durable plan records, state versions, idempotency keys, workflow/work-graph IDs, envelope decisions, and objective digests. It does not store plaintext objectives in the local plan table. Verified Host integrations may add event, projection, artifact, and evaluation stores under separate authority.

## Upgrade and uninstall

Plugin upgrades do not erase state because the state root is external. `codex plugin remove` also leaves state intact. Keep it while you need audit history or resumable work.

Before removing any state file, stop active Router processes and verify that no Goal depends on it. Remove only the explicit file or directory you have reviewed; the project never treats uninstall as permission for silent recursive deletion.

## Inspect readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

No telemetry is enabled by default. A configured model adapter can use provider quota; its evidence and retention policy must be disclosed separately.
