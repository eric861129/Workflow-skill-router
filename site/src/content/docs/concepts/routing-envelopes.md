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

A Managed Goal work item may use `single` or `phased` as its inner envelope. Classification follows a fixed order:

1. Goal status and side questions are classified first as control/read-only requests, not new execution work.
2. Native Goal progress or steer establishes the outer `managed-goal` envelope.
3. For a detached request or the current work item, `requested_work_mode`, the deterministic analyzer, a deterministic Profile route, and the builtin fallback choose the inner envelope, in that order.

The structural analyzer records `classifier_revision: deterministic-objective-v1`, `classification_source`, and `classification_reason_codes`. It evaluates bounded signals such as stages, dependencies, and resumability. It does not claim to understand every task semantically, and classification never authorizes a Skill, tool, or side effect. A semantic adapter may suggest a reviewable candidate but cannot directly rewrite a persisted route.

<a id="example"></a>
## State, input, and output example

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {
    "execution_kind": "routed-work",
    "envelope": "phased",
    "classifier_revision": "deterministic-objective-v1",
    "classification_source": "deterministic-analyzer",
    "classification_reason_codes": ["multiple-distinct-stages"]
  },
  "phases": ["design", "implement", "verify"]
}
```

<a id="runtime-readiness"></a>
## Runtime readiness

### Current bundled R0 (`current-bundled-r0`)

| Current class | Tools | What it means |
| --- | --- | --- |
| `local-ready` (4) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Bundled R0 supports their documented Router-local scope. |
| `verified-host` (5) | `sync_runtime_context`, `get_next_work`, `validate_route`, `record_work_event`, `evaluate_gate` | Requires verified Host state, policy, and receipts; local calls fail closed. |
| `configured-adapter` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Requires a server-configured adapter, authorization, and applicable attestation. |

### Target beta.5 (`target-beta.5`)

`conditional-local` is a beta.5 target and is **not available in current bundled R0**.

| Target class | Tools | What it would mean |
| --- | --- | --- |
| `local-ready` (4) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Unchanged Router-local R0 operations. |
| `conditional-local` (3) | `get_next_work`, `record_work_event`, `evaluate_gate` | Router-owned graphs and local advisory evidence only; outputs use `authority_mode=router-local` and `host_transition_authorized=false`. |
| `verified-host` (2) | `sync_runtime_context`, `validate_route` | Host authority remains mandatory. |
| `configured-adapter` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Configured-adapter authority remains mandatory. |

Host-authoritative state uses a separate `authority_mode=verified-host`; configured evaluation uses `authority_mode=configured-adapter`. Today, the three beta.5 target tools still require the verified Host. GA does not mean all 12 tools are locally usable.

<a id="failure-modes"></a>
## Failure modes

- A large request forced into `single` loses phase-specific capability and evidence checks.
- A copy edit forced into `managed-goal` creates needless state and consent overhead.
- Reusing one route across phases keeps stale capabilities active after the work changes.
- In current bundled R0, local `get_next_work`, `record_work_event`, and `evaluate_gate` calls fail closed with a verified-Host requirement and do not run.
- Under the beta.5 target, a local request that targets native Goal progress or steer still fails closed with a verified-Host requirement and does not mutate native Codex Goal.
- If the beta.5 Router-local gate target is implemented, a passing local gate is only advisory. It does not activate a Skill, authorize a native Goal transition, or grant deployment or production permission.
- Without the required receipt, configured adapter, consent, or Explicit Skill Lock condition, the protected operation does not run.

<a id="security-boundary"></a>
## Security and authority boundary

Envelope classification does not grant tool permission. Every route still passes capability, risk, consent, Explicit Skill Lock, and Host approval checks. Router-local state never claims Skill activation or changes native Goal state. The model cannot use “Goal mode” to widen repository, deployment, production, or communication authority.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_profiler tests.routing.test_explicit_skill_scenarios -v
```
