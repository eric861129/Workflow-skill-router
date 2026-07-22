---
title: Troubleshooting V2
description: Diagnose installation, runtime readiness, routing, state, and evaluation failures without bypassing safety boundaries.
---

## Start with `doctor`

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

Confirm the runtime profile, telemetry state, Python version, content preflight result, state path, and per-tool readiness. `bundled-local-r0` truthfully means local planning and status—not full Host orchestration.

## Plugin does not appear

```powershell
codex plugin list
```

For a normal installation, ensure the marketplace is pinned to `v2.0.0-beta.3`, reinstall `workflow-skill-router@workflow-skill-router`, and restart Codex. For a contributor checkout, ensure the marketplace points at the repository root before reinstalling.

## Plugin startup fails

If the error says that the Python Runtime is unavailable and the MCP server cannot start, the Plugin does not automatically fall back to Skill-only mode. Install or choose the standalone Skill-only mode yourself after the startup error.

If the error instead says that MCP startup failed, treat it as a state-path, filesystem-permission, or Plugin-installation problem—not a Python diagnosis. Check the configured local state directory, its permissions, and the Plugin installation, then retry.

If the Runtime crashes after startup, requests in that bridge generation return an error and a retry may be necessary. This is not a high-availability guarantee.

## Skill-only does not trigger

Verify that the folder directly contains `SKILL.md`:

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path (Join-Path $Router "SKILL.md")
Get-Content -Encoding UTF8 (Join-Path $Router "SKILL.md") | Select-Object -First 8
```

Start a new task after installation. Skill-only must declare `skill-only-fallback`; it cannot expose MCP tools by itself.

## Tool returns `capability-unavailable`

This is a typed, expected result. Read `runtime_requirement`, `required_capabilities`, and `fallback_action`. Do not fabricate Host authority or relabel the tool as local-ready.

In the unreleased source checkout, `get_next_work`, `record_work_event`, and `evaluate_gate` are `conditional-local` only when a validated Router-owned graph exists and no Native Goal authority is present. They return Router-local scheduling, reported local progress, or an advisory local gate; they do not verify Skill activation or authorize a Host transition. A missing graph returns `router-owned-work-graph` so the caller can create or replay that local graph. A corrupt graph returns a public-safe `internal-error`, never an invented Host fallback. Native Goal work uses its tool-specific verified-host capabilities instead.

`validate_route` remains `verified-host-required` in every branch. `sync_runtime_context` also requires verified Host authority, while evaluation tools require a configured adapter.

## Explicit Skill Lock asks too often

Consent is required only when the user explicitly named SKILLs and the Router proposes support outside that lock. If no SKILL was named, the Router should auto-route the minimal justified set and declare it before execution.

## State or resume problems

Check `WORKFLOW_SKILL_ROUTER_DATA_DIR` and the platform default in [Local State](/Workflow-skill-router/reference/local-state/). A state directory inside the Plugin installation/cache boundary is rejected. Stop active Router processes before inspecting or removing a reviewed state file.

## Evaluation will not run

Live execution requires an operator-configured absolute executable path and `--confirm-live-run`. A dry-run or fixture is not Behavior evidence. A corrected live run also requires explicit quota authorization; do not retry an old superseded run and present it as current proof.

## Site or docs validation fails

```powershell
python scripts/check-doc-parity.py
python scripts/check-markdown-links.py .
node scripts/build-mcp-reference-data.mjs --check
Set-Location site
npm run build
```

Fix source contracts or source docs. Do not hand-edit generated MCP reference data or release archives.

## Report an issue

Include the operating system, runtime profile, exact command, sanitized error, and whether you used Plugin or Skill-only. Exclude tokens, raw model traces, private paths, customer names, and internal repository data.
