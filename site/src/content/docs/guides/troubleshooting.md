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

For a normal installation, ensure the marketplace is pinned to `v2.0.0-beta.2`, reinstall `workflow-skill-router@workflow-skill-router`, and restart Codex. For a contributor checkout, ensure the marketplace points at the repository root before reinstalling.

## Skill-only does not trigger

Verify that the folder directly contains `SKILL.md`:

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path (Join-Path $Router "SKILL.md")
Get-Content -Encoding UTF8 (Join-Path $Router "SKILL.md") | Select-Object -First 8
```

Start a new task after installation. Skill-only must declare `skill-only-fallback`; it cannot expose MCP tools by itself.

## Tool returns `capability-unavailable`

This is a typed, expected result. Read `runtime_requirement`, `required_capabilities`, and `fallback_action`. Do not fabricate Host authority or relabel the tool as local-ready. `get_next_work`, protected route validation, events, and gates need verified Host ports; evaluation tools need a configured adapter.

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
