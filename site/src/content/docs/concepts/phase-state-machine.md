---
title: Phase State Machine
description: Advance work only when state, evidence, and side effects agree.
---

<a id="problem"></a>
## Problem

An agent can say a phase is complete while evidence is stale, a side effect is unknown, or another process has changed the plan. Free-form status text cannot protect long-running work from those races.

<a id="contract"></a>
## Contract

The main path is `pending -> ready -> active -> verifying -> completed`. Waiting and recovery use `paused`, `awaiting-approval`, and `rerouting`; terminal phases are `completed`, `skipped`, or `failed`. Every transition binds expected state version, plan revision, and evidence digest.

Entering `active` requires entry conditions, a valid route/lease, and runtime approval. Unknown side effects block `verifying`; failed mandatory gates block `completed`.

<a id="example"></a>
## State, input, and output example

```json
{
  "current": {"status": "active", "state_version": 7, "plan_revision": 2},
  "request": {"target": "verifying", "expected_state_version": 7, "expected_plan_revision": 2},
  "context": {"unknown_side_effect": false},
  "event": "PHASE_STATUS_TRANSITIONED"
}
```

<a id="failure-modes"></a>
## Failure modes

- State, plan, or evidence drift rejects the transition as a concurrency conflict.
- Terminal phases cannot reopen.
- A paused phase resumes through `rerouting`, so capabilities and evidence refresh first.
- Advisory checks cannot offset a mandatory gate failure.

<a id="security-boundary"></a>
## Security and authority boundary

Clients submit semantic observations, not raw authoritative events or pass/fail claims. The core derives state changes and validates activation receipts. The host controls approval and verified side-effect outcomes.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.workflow.test_transitions tests.workflow.test_gates -v
```
