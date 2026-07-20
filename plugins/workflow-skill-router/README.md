# Workflow Skill Router V2 Plugin

Runtime-aware routing for Single, Phased, and Managed Goal work in Codex. The Plugin packages the canonical Router SKILL, a deterministic MCP server, and the local R0 Python control plane. Capabilities that require a verified host or configured model adapter fail closed instead of pretending to be locally available.

## Requirements

- Codex with Plugin and MCP support
- Python 3.11 or newer
- Node.js 24 or newer

The released Plugin already contains the MCP bundle and Python runtime archive. npm is required only when rebuilding from source.

## Install in Codex

Install the published immutable `v2.0.0-beta.1` Git marketplace snapshot:

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Restart Codex or open a new Codex task, then ask Codex to show the Workflow Skill Router status. Expect the `bundled-local-r0` runtime label, twelve MCP tools, and four local-ready tools.

For a contributor checkout, run this from the repository root:

```powershell
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Use the tagged snapshot for normal installations. Use the checkout path only when developing or testing repository changes.

## Verify the MCP server

For deep verification of an extracted package, run the bundled Python runtime check from the Plugin directory:

```powershell
python runtime/workflow_skill_router.pyz doctor
```

Repository contributors can run the full extracted-package handshake from the repository root:

```powershell
node plugins/workflow-skill-router/scripts/smoke-plugin.mjs path/to/extracted/workflow-skill-router
```

The smoke verifies the manifest, canonical SKILL, twelve MCP tool names, external state boundary, and a real stdio MCP initialize/tools-list exchange. Runtime readiness is authoritative: the bundled local R0 profile does not imply that every public tool is locally executable.

## Skill-only fallback

If Plugin or MCP loading is unavailable, install the separate `workflow-skill-router-skill-v2.0.0-beta.1.zip` GitHub Release asset into the Codex Skills directory. Skill-only mode preserves routing instructions and Explicit Skill Lock, but scoped consent remains advisory because there is no persisted proposal or deterministic transition. It also has no durable resume, CAS, complete drift detection, or sealed activation instrumentation, and must not be reported as `hybrid-full`.

## Local state and privacy

State is stored outside the Plugin cache:

- Windows: `%LOCALAPPDATA%\Codex\workflow-skill-router`
- macOS: `~/Library/Application Support/Codex/workflow-skill-router`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router`

Set `WORKFLOW_SKILL_ROUTER_DATA_DIR` to choose another external state directory. The Router has no default telemetry and does not send local workflow state to a remote service. A configured real-model evaluation adapter may use provider quota; its execution and evidence boundary must be explicitly disclosed.

## Uninstall

```powershell
codex plugin remove workflow-skill-router@workflow-skill-router
```

Uninstalling the Plugin does not silently delete Router state. Review and remove the external state directory separately only when its audit history is no longer needed.

## Troubleshooting

- `python-3.11-unavailable`: install Python 3.11+ or set `WORKFLOW_SKILL_ROUTER_PYTHON` to one executable path.
- MCP server does not start: confirm `node --version` reports Node.js 24+ and rerun the extracted-package smoke.
- `capability-unavailable`: read the returned requirement and fallback; the tool needs a verified host or configured adapter.
- State path is rejected: choose a directory outside the Plugin installation/cache path.
- Plugin is not listed: confirm the marketplace name is `workflow-skill-router`, then rerun `codex plugin list`.

Source, issues, and security policy: <https://github.com/eric861129/Workflow-skill-router>
