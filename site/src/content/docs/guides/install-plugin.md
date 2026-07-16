---
title: Install the Plugin + MCP runtime
description: Install, verify, and remove the Workflow Skill Router V2 Plugin without overstating local capabilities.
---

## Requirements

- Codex with Plugin and MCP support
- Python 3.11 or newer
- Node.js 24 or newer

The released archive includes the MCP bundle and Python runtime. npm is required only for a source rebuild.

## Contributor checkout

Use this path before the immutable beta tag exists:

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

## Tagged marketplace snapshot

Use this only after `v2.0.0-beta.1` is published:

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

## Verify

From the repository checkout:

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
node plugins/workflow-skill-router/scripts/smoke-plugin.mjs path/to/extracted/workflow-skill-router
```

`doctor` must report `bundled-local-r0`, telemetry disabled, and a per-tool readiness matrix. The extracted-package smoke verifies the manifest, canonical SKILL, ten tool names, external state boundary, and a real MCP initialize/tools-list exchange.

## What works locally

`plan_work` and `get_router_status` are local-ready. Scheduling, protected route validation, work events, and gates require verified Host capabilities. Model evaluation tools require a configured adapter. An unavailable call returns `capability-unavailable` with its requirement and fallback.

## Uninstall

```powershell
codex plugin remove workflow-skill-router@workflow-skill-router
```

Uninstalling does not delete external Router state. Review the [local state guide](/Workflow-skill-router/reference/local-state/) before removing audit history.
