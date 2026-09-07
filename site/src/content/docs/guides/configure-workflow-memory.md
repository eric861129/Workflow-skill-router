---
title: Configure Workflow Memory
description: Configure local Memory policy, privacy, retention and managed promotion without authority escalation.
---

Adaptive Workflow Memory is **default-off**. Begin by checking status; do not create a policy merely to inspect the current state.

```bash
workflow-skill-router memory status
workflow-skill-router memory policy explain
```

## Data root and fixed sources

The Plugin keeps durable state outside its installation cache. Typical data roots are `%LOCALAPPDATA%\workflow-skill-router` on Windows, `~/Library/Application Support/workflow-skill-router` on macOS, and `${XDG_DATA_HOME:-~/.local/share}/workflow-skill-router` on Linux. The configured data-root environment override takes precedence. Public-safe status output reports source state and Digests, not an absolute local path.

Personal policy is read from the fixed supported Memory Policy filenames under the data root. Workspace policy is read only from the fixed `.codex` location under an MCP Client-advertised or operator-trusted Workspace root. Two supported formats at the same scope are ambiguous and fail closed; a Workspace symlink cannot redirect discovery.

Resolution is `disabled < observe < reviewed < automatic`: Personal sets the ceiling and **Workspace cannot elevate Personal**. A Workspace policy may disable capture, lower a feature to `observe`, narrow risk or target sets, shorten retention, or disallow free text.

## Copy-paste policies

The canonical source and packaged Plugin contain:

```text
assets/memory-policy.disabled.example.yaml
assets/memory-policy.reviewed.example.yaml
assets/memory-policy.automatic.example.yaml
```

The `.yaml` examples intentionally use JSON syntax, which is inside the supported safe-YAML subset. Duplicate keys, aliases, tags, executable values and unknown fields are rejected. Start from the disabled example and change only documented fields.

Feature overrides may reduce a preset but cannot exceed it. `automatic` requires versioning, Backtest and visible promotion disclosure; automatic targets remain `managed-personal` and `managed-workspace-local`. It never grants User-owned Profile or Host write authority.

## Privacy, retention and purge

Do not retain raw objectives, secrets or local paths. Typed feedback is the normal path; free text requires explicit privacy opt-in at both policy and operation boundaries. Retention is applied deterministically: expired observations are removed first, then the oldest excess records.

Use status or summary to obtain the current Digest before destructive purge. `purge_workflow_memory` requires `confirmed: true` plus that expected Digest. `history-only` and `analytics-only` remove optional Memory rows while preserving the schema. Purge does not delete a User-owned Profile and does not silently delete a Managed Profile.

## Recommended rollout

Use `observe -> reviewed -> automatic`. Keep each step long enough to inspect corrections, suppression and Backtest results. `automatic` is an explicit local promotion operation, **no background learning** or daemon. There is **no telemetry**.

A `skill-only` install cannot claim durable state or run these MCP transitions; use Plugin + MCP for durable Memory. Routes without receipt evidence remain `intended-unverified`, and Skill consistency is unavailable.


Contract vocabulary: `default-off`; `disabled < observe < reviewed < automatic`;
`Workspace cannot elevate Personal`; `automatic-managed`; `intended-unverified`;
`no telemetry`; `no background learning`; User-owned Profile; purge; `skill-only`;
and the recommended sequence `observe -> reviewed -> automatic`.
