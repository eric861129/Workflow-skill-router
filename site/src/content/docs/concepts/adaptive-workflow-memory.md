---
title: Adaptive Workflow Memory
description: An opt-in, local-first memory layer that learns repeatable routing without taking ownership away from the user.
---

Adaptive Workflow Memory turns repeated, successful routing outcomes into reviewable routing knowledge. It is deliberately **default-off**. Installing the Plugin or exposing the twenty MCP tools does not start capture, create the Optional Memory DB, change a Profile, or send telemetry.

## Four autonomy levels

| Mode | What the Router may do | What it may not do |
| --- | --- | --- |
| `disabled` | Report that Memory is off. | Capture history or create optional state. |
| `observe` | Record eligible, redacted local observations and typed feedback. | Create or apply a Profile proposal. |
| `reviewed` | Build Candidates, Diff previews and Backtests for explicit approval. | Apply a proposal before the bound preview is approved. |
| `automatic` | Promote only high-confidence `automatic-managed` Candidates into Router-managed Profiles during an explicit local promotion pass. | Write a User-owned Profile, bypass a manual conflict, or claim a background scheduler. |

The order is `disabled < observe < reviewed < automatic`. A Personal policy sets the autonomy ceiling. A Workspace policy may reduce that ceiling for the current Workspace, but **Workspace cannot elevate Personal**.

## Ownership remains explicit

Routing precedence stays:

```text
Explicit Skill Lock
-> User-owned Workspace Profile
-> Router-managed Workspace-local Profile
-> User-owned Personal Profile
-> Router-managed Personal Profile
-> Built-in routing
```

Automatic promotion can target only `managed-personal` or `managed-workspace-local`. A manual conflict suppresses the Candidate; it does not rewrite the User-owned Profile or silently fall through to another route.

## From observation to a managed rule

1. A completed Router-owned workflow is reduced to bounded observations. Raw objectives, secrets and local paths are not Memory inputs.
2. Typed feedback can mark the route accepted, corrected or rejected. Free text remains separately double-opted-in and is never required.
3. Repeated evidence may produce a Candidate. R3 work, unknown Side-effect classes and unknown Skills stay review-only or ineligible.
4. `preview_profile_update` produces an exact Profile/Diff/Backtest binding without writing a Proposal or Profile.
5. Approval revalidates the Candidate, Policy, expected Profile and Backtest before CAS/Revision/atomic materialization.
6. Rollback is a new forward Revision and remains reviewable; it is not a hidden history rewrite.

A selected Skill without verified activation or receipt evidence is reported as `intended-unverified`. **Skill consistency is unavailable without receipt evidence**; planned intent is not execution proof.

## Local-first privacy boundary

The Operational DB and Optional Memory DB are separate. Memory uses bounded identifiers, Digests, reason codes and aggregate metrics. There is **no telemetry** and **no background learning**. Export and purge are explicit operations. Supported purge scopes remove optional history or analytics while preserving schema and User-owned Profiles. Managed Profile deletion is not implied by purge.

The `skill-only` installation can explain policy files but cannot honestly claim durable Memory, MCP review transitions or Host-authorized Workspace writes. Durable Memory requires the Plugin + MCP runtime.


Contract vocabulary: `default-off`; `disabled < observe < reviewed < automatic`;
`Workspace cannot elevate Personal`; `automatic-managed`; `intended-unverified`;
`no telemetry`; `no background learning`; User-owned Profile; purge; `skill-only`;
and the recommended sequence `observe -> reviewed -> automatic`.
