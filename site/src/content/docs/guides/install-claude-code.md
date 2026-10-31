---
title: Install for Claude Code
description: Install, verify, and remove the Workflow Skill Router Plugin in Claude Code while sharing Profiles with Codex.
---

Claude Code support ships with the prepared 2.1.0 candidate. It is not part of the published `v2.0.2` release, so install it from the repository's default branch.

## Requirements

- Claude Code with Plugin support
- Node.js 24 or newer on the `PATH` that launches Claude Code
- Python 3.11 or newer

The Plugin contains the MCP bundle and Python runtime archive. It ships no `package.json`, so Claude Code installs no npm dependencies.

## Install from the marketplace

Run these commands inside Claude Code:

```text
/plugin marketplace add eric861129/Workflow-skill-router
/plugin install workflow-skill-router@workflow-skill-router
```

Or run them from a shell:

```sh
claude plugin marketplace add eric861129/Workflow-skill-router
claude plugin install workflow-skill-router@workflow-skill-router
```

The Plugin manifest carries the product version, so Claude Code offers an update when that version changes. Update with `claude plugin update workflow-skill-router@workflow-skill-router`.

## Load a development checkout

To test repository changes without installing them, start Claude Code from the repository root with the Plugin directory:

```sh
claude --plugin-dir plugins/claude-code/workflow-skill-router
```

Run `python scripts/sync-claude-plugin.py` first if you changed the MCP server, the Python core, or the canonical Skill references. CI runs the same script with `--check`.

## Verify

1. Run `/mcp` and confirm that `plugin:workflow-skill-router:workflow-skill-router` is connected.
2. Ask Claude Code: **"Show the Workflow Skill Router status and explain which capabilities are available in this environment."** The answer should come from `get_router_status` and show `bundled-local-r0`.
3. For an offline check, run the bundled runtime with the host set. The output must include `"host": "claude-code"`.

```sh
WORKFLOW_SKILL_ROUTER_HOST=claude-code python plugins/claude-code/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

If `/mcp` reports a failed server, Claude Code could not start Node.js or the runtime could not find Python 3.11+. The SKILL then runs as `skill-only-fallback` and must not claim durable state.

## How Claude Code differs from Codex

| Topic | Claude Code behavior |
| --- | --- |
| Host setting | The Plugin's `.mcp.json` sets `WORKFLOW_SKILL_ROUTER_HOST=claude-code`. An unknown value stops the MCP server before it reads any workspace file. |
| Workspace Profile | `.claude/workflow-skill-router.json` first, then `.codex/workflow-skill-router.json`. Workspace Memory policy files use the same order. |
| Personal Profiles and state | Shared with the Codex Plugin in the same external data directory. `WORKFLOW_SKILL_ROUTER_DATA_DIR` still overrides it. |
| Native Goal | Claude Code has none. Managed Goal work uses only the Router-owned local work graph and reports `authority_mode=router-local`. |
| Tool names | `mcp__plugin_workflow-skill-router_workflow-skill-router__<tool>` |
| Workspace trust | The server reads workspace files only inside MCP Client roots or `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`. |

A repository used from both hosts can keep one `.codex/workflow-skill-router.json`. Add `.claude/workflow-skill-router.json` only when Claude Code needs a different Skill Tree.

## Uninstall

```sh
claude plugin uninstall workflow-skill-router@workflow-skill-router
```

Router state lives outside the Plugin cache, so uninstalling keeps your Profiles, plans, and consent history. Review the [local state guide](/Workflow-skill-router/reference/local-state/) before removing audit history.
