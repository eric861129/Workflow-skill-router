---
title: Install the Plugin + MCP runtime
description: Install, verify, and remove the Workflow Skill Router V2 Plugin without overstating local capabilities.
---

## Requirements

- Codex with Plugin and MCP support
- Python 3.11 or newer
- Node.js 24 or newer

The released archive includes the MCP bundle and Python runtime. npm is required only for a source rebuild.

## Tagged marketplace snapshot

Use the immutable `v2.0.0-beta.2` snapshot for normal installations:

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.2
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Restart Codex or open a new task after changing Plugin registration. Ask Codex to show the Workflow Skill Router status; the response should report `bundled-local-r0` and expose the Router MCP tools.

## Contributor checkout

Use a checkout only when developing or testing repository changes:

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

## Deep verification from source or an extracted ZIP

Run these checks from a repository checkout. Replace `path/to/extracted/workflow-skill-router` with the extracted Plugin directory when inspecting the release ZIP:

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
node plugins/workflow-skill-router/scripts/smoke-plugin.mjs path/to/extracted/workflow-skill-router
```

`doctor` must report `bundled-local-r0`, telemetry disabled, and a per-tool readiness matrix. The extracted-package smoke verifies the manifest, canonical SKILL, twelve tool names, external state boundary, and a real MCP initialize/tools-list exchange.

## What works locally

The bundled local R0 runtime in `v2.0.0-beta.2` supports Personal Routing Profile validation, installation, listing, and preview. From a contributor checkout, install the packaged personal example and preview it:

```powershell
Copy-Item starter/v2/workflow-skill-router/assets/personal-routing-profile.example.json ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api
```

For project policy, copy `starter/v2/workflow-skill-router/assets/workspace-routing-profile.example.json` to `.codex/workflow-skill-router.json`, then add `--workspace-root (Get-Location).Path` to `profile preview`. Do not put the personal example at the workspace path unchanged.

Profiles stay outside the Plugin cache. Their output is `intended-unverified` until Runtime Capability Discovery validates each selected SKILL.

`plan_work`, `propose_support_consent`, `transition_support_consent`, and `get_router_status` are local-ready. Scheduling, protected route validation, work events, and gates require verified Host capabilities. Model evaluation tools require a configured adapter. An unavailable call returns `capability-unavailable` with its requirement and fallback.

## Uninstall

```powershell
codex plugin remove workflow-skill-router@workflow-skill-router
```

Uninstalling does not delete external Router state. Review the [local state guide](/Workflow-skill-router/reference/local-state/) before removing audit history.
