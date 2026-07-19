---
title: Routing Envelopes
description: Choose Single, Phased, or Managed Goal without over-routing.
---

<a id="problem"></a>
## Problem

Treating every request as one step hides verification boundaries; treating every request as a project adds planning overhead and prompt fatigue. The Router needs the smallest structure that preserves meaningful dependencies.

<a id="contract"></a>
## Contract

- `single`: one bounded intent, one stage, no resumable dependency graph.
- `phased`: two or more distinct stages or domains; every phase reroutes independently.
- `managed-goal`: resumable, cross-repository, multi-milestone, dependency-DAG work, or active Goal progress/steer.

A Managed Goal work item may override its inner envelope to `single` or `phased`. Goal status and side questions are control/read-only requests, not new Managed Goal work.

<a id="example"></a>
## State, input, and output example

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {"execution_kind": "routed-work", "envelope": "phased"},
  "phases": ["design", "implement", "verify"]
}
```

<a id="failure-modes"></a>
## Failure modes

- A large request forced into `single` loses phase-specific capability and evidence checks.
- A copy edit forced into `managed-goal` creates needless state and consent overhead.
- Reusing one route across phases keeps stale capabilities active after the work changes.

<a id="security-boundary"></a>
## Security and authority boundary

Envelope classification does not grant tool permission. Every route still passes capability, risk, consent, and host approval checks. The model cannot use “Goal mode” to widen repository, production, or communication authority.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_profiler tests.routing.test_explicit_skill_scenarios -v
```
