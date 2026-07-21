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

Personal Routing Profile files live under `profiles/personal/*.json` inside the same external data root. Workspace Profiles remain project-owned at `.codex/workflow-skill-router.json`; the Router reads only that fixed path, and MCP mode requires the root to be advertised by the Client or configured in `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`. Profile files never belong in the Plugin cache.

Profile content is strict routing data, not executable instructions. Invalid existing files fail closed. A valid match is still `intended-unverified` until Runtime Capability Discovery checks the selected SKILLs.

Bundled local R0 stores durable plan records, state versions, idempotency keys, workflow/work-graph IDs, envelope decisions, and objective digests. It does not store plaintext objectives in the local plan table. Verified Host integrations may add event, projection, artifact, and evaluation stores under separate authority.

## Upgrade and uninstall

The state root resolves outside the Plugin installation/cache boundary. The automated local-root replacement rehearsal verifies resolver continuity while that external path is retained. It does not prove that a real `codex plugin remove` followed by reinstall preserves state, and Windows/macOS/Linux lifecycle verification remains release-candidate migration evidence that has not yet been completed.

Keep the external state path while you need audit history or resumable work. Before an upgrade or uninstall workflow, record the exact path and treat any state preservation outcome as unverified until the corresponding lifecycle evidence exists.

Before removing any state file, stop active Router processes and verify that no Goal depends on it. Remove only the explicit file or directory you have reviewed; the project never treats uninstall as permission for silent recursive deletion.

## Inspect readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

No telemetry is enabled by default. A configured model adapter can use provider quota; its evidence and retention policy must be disclosed separately.
