---
title: Migrate to Workflow Memory
description: Adopt Adaptive Workflow Memory gradually without changing existing routing ownership.
---

Existing installations stay **default-off** after upgrade. Migration changes no User-owned Profile and creates no Optional Memory DB until an enabled policy reaches a write operation.

## 1. Establish a clean baseline

Update the Plugin, run `memory status`, validate current Personal and Workspace policies, and export only public-safe configuration metadata needed for review. Preserve existing Personal Routing Profiles; Memory is an additional managed layer, not a replacement.

## 2. Observe

Enable `observe` first. Confirm that only eligible Router-owned completions are recorded, R3 and unknown Side-effect work remain excluded, and raw objectives, paths and secrets never appear. Review aggregate metrics and correction rates. Routes lacking activation receipts remain `intended-unverified`; Skill consistency is unavailable without receipt evidence.

## 3. Review proposals

Move to `reviewed` only after the observation sample is representative. Inspect Candidate evidence, exact Profile Diff and Backtest. Approval must reference the same bound preview. Rejection suppresses unchanged evidence; it does not write or select a fallback route.

## 4. Consider automatic managed promotion

Move from `reviewed` to `automatic` only after repeated clean approvals. The autonomy order is `disabled < observe < reviewed < automatic`, and **Workspace cannot elevate Personal**. Automatic writes are `automatic-managed` and target only `managed-personal` or `managed-workspace-local`; manual conflicts suppress the Candidate.

Automatic promotion remains an explicit local pass with visible notification—**no background learning**, scheduler or telemetry. Runtime and Side-effect authority do not change.

## 5. Rehearse rollback and purge

Rollback creates a new reviewable forward Revision and preserves history. Purge requires explicit confirmation and a current Digest; history/analytics purge does not delete a User-owned Profile. Disabling Memory stops future capture but does not silently purge existing data.

## Recommended sequence

Use `observe -> reviewed -> automatic`, with a review checkpoint between every transition. Return to `disabled` immediately if evidence, privacy or ownership assumptions no longer hold.

A `skill-only` installation may use this guide to prepare configuration, but cannot claim durable Memory or MCP review transitions. Plugin + MCP is required for the operational workflow. There is **no telemetry**.


Contract vocabulary: `default-off`; `disabled < observe < reviewed < automatic`;
`Workspace cannot elevate Personal`; `automatic-managed`; `intended-unverified`;
`no telemetry`; `no background learning`; User-owned Profile; purge; `skill-only`;
and the recommended sequence `observe -> reviewed -> automatic`.
