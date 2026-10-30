# Workflow Skill Router V2 for Claude Code

Workflow Skill Router picks the Skill that should lead the current phase of a task, adds only the support that phase needs, and shows the route before Claude continues. You save your workflow once as a Profile (a lead Skill, up to three support Skills, and an exit gate per phase), and the same Profile works in Claude Code and Codex. When you name a Skill, it leads, and support outside your choice waits for your consent. A local MCP server keeps plans, consent records, and Router-owned work graphs on your machine.

This Plugin packages a Claude Code version of the Router SKILL, the same deterministic MCP server used by the Codex Plugin, and the local R0 Python control plane. Capabilities that require a verified host or configured model adapter fail closed instead of pretending to be locally available.

Claude Code support ships with the prepared 2.1.0 candidate. It is not part of the published `v2.0.2` release.

## Requirements

- Claude Code with Plugin support
- Node.js 24 or newer on the `PATH` that launches Claude Code
- Python 3.11 or newer (`py -3.11` or `python` on Windows, `python3` or `python` elsewhere)

The Plugin already contains the MCP bundle and Python runtime archive. It ships no `package.json`, so Claude Code installs no npm dependencies, and it does not install, activate, or download other Skills or packages.

The Plugin starts a local stdio MCP server, `node ${CLAUDE_PLUGIN_ROOT}/mcp/server.bundle.mjs`, which runs the bundled Python runtime `runtime/workflow_skill_router.pyz`. It works fully in Claude Code (terminal, IDE, and the desktop Code tab). Where local MCP servers are not loaded, such as claude.ai chat, only the Skill loads and runs as `skill-only-fallback`: routing instructions without durable state.

## Privacy

The Plugin stores plans, consent records, Profiles, and work-graph events in a local data directory outside the Plugin cache (`%LOCALAPPDATA%\Codex\workflow-skill-router` on Windows, `~/Library/Application Support/Codex/workflow-skill-router` on macOS, `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` on Linux). Plans store a digest of the objective, not the plaintext. The Plugin makes no network calls and has no telemetry. Workflow Memory is off by default.

## Install

In Claude Code:

```text
/plugin marketplace add eric861129/Workflow-skill-router
/plugin install workflow-skill-router@workflow-skill-router
```

From a shell:

```sh
claude plugin marketplace add eric861129/Workflow-skill-router
claude plugin install workflow-skill-router@workflow-skill-router
```

The Plugin manifest carries the product version, so Claude Code offers an update when that version changes. Run `claude plugin update workflow-skill-router@workflow-skill-router` to pick it up.

To load a contributor checkout without installing it, run Claude Code with `claude --plugin-dir plugins/claude-code/workflow-skill-router` from the repository root.

## Verify

1. Run `/mcp` and confirm that `plugin:workflow-skill-router:workflow-skill-router` is connected.
2. Ask Claude Code to show the Workflow Skill Router status. Expect the `bundled-local-r0` runtime label from `get_router_status`.
3. For an offline check, run the bundled runtime from the installed Plugin directory with the host set:

```sh
WORKFLOW_SKILL_ROUTER_HOST=claude-code python runtime/workflow_skill_router.pyz doctor
```

The `doctor` output reports `"host": "claude-code"`.

## What differs from the Codex Plugin

| Topic | Claude Code |
| --- | --- |
| Host setting | `.mcp.json` sets `WORKFLOW_SKILL_ROUTER_HOST=claude-code`. An unknown value stops the MCP server before it reads any workspace file. |
| Workspace Profile | `.claude/workflow-skill-router.json` first, then `.codex/workflow-skill-router.json`. Workspace Memory policy uses the same order. |
| Personal Profiles and state | Shared with the Codex Plugin in the same external data directory, so one Skill Tree works in both hosts. `WORKFLOW_SKILL_ROUTER_DATA_DIR` still overrides it. |
| Native Goal | Claude Code has none. Managed Goal work uses only the Router-owned local work graph and reports `authority_mode=router-local`. |
| Tool names | `mcp__plugin_workflow-skill-router_workflow-skill-router__<tool>` |
| Workspace trust | The server accepts only MCP Client roots or `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`. Model-supplied paths outside them fail closed. |

The default data directory is outside the Plugin cache, so uninstalling or updating the Plugin keeps your Profiles, plans, and consent history.

## Source of truth

This directory is generated in part. `.claude-plugin/plugin.json`, `.mcp.json`, `README.md`, `assets/icon.png`, and `skills/workflow-skill-router/SKILL.md` are maintained by hand. Everything else is copied byte-for-byte from the Codex Plugin and the canonical Skill by `python scripts/sync-claude-plugin.py`. CI runs it with `--check`.
