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

The structural analyzer records `classifier_revision: deterministic-objective-v2`, `classification_source`, and `classification_reason_codes`. It evaluates bounded signals such as stages, dependencies, and resumability. It does not claim to understand every task semantically, and classification never authorizes a Skill, tool, or side effect. A semantic adapter may suggest a reviewable candidate but cannot directly rewrite a persisted route.

`deterministic-objective-v2` adds common Traditional Chinese repair, requirements, cross-project, and progress-retention signals, and ignores negated long-running signals. Existing records retain their original classifier revision on replay.

<a id="example"></a>
## State, input, and output example

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {
    "execution_kind": "routed-work",
    "envelope": "phased",
    "classifier_revision": "deterministic-objective-v2",
    "classification_source": "deterministic-analyzer",
    "classification_reason_codes": ["multiple-distinct-stages"]
  },
  "phases": ["design", "implement", "verify"]
}
```

<a id="runtime-readiness"></a>
## Runtime readiness

### Previous release (`published-v2.0.2`)

`v2.0.2` has 12 tools: **4 always local-ready + 3 Router-owned conditional-local**, 2 verified-Host-required, and 3 configured-adapter-required. The release includes the local work loop, but not the later Adaptive Workflow Memory implementation.

### v2.1.x and development branch (`development-main`)

`v2.1.0` adds 8 Memory tools, for 20 total; Memory is default-off. This table describes `v2.1.1` and the current checkout.

| Availability | Tools | Conditions |
| --- | --- | --- |
| `local-ready` (10) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status`, `get_memory_status`, `remember_workflow`, `record_route_feedback`, `list_workflow_candidates`, `preview_profile_update`, `purge_workflow_memory` | Local tools still enforce input, policy, and confirmation requirements; readiness is not blanket side-effect authorization. |
| `conditional-local` (5) | `get_next_work`, `record_work_event`, `evaluate_gate`, `transition_profile_update`, `rollback_profile_revision` | Requires a Router-owned graph or a policy-bound local Profile operation; local work-loop calls report `authority_mode=router-local`. `get_next_work` reports `host_goal_mutated=false`; event and gate calls report `host_transition_authorized=false`. |
| `verified-host-required` (2) | `sync_runtime_context`, `validate_route` | Verified Host authority remains mandatory. |
| `configured-adapter-required` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | A configured evaluation adapter and authorization remain mandatory. |

| Condition | `get_next_work` | `record_work_event` | `evaluate_gate` |
| --- | --- | --- | --- |
| Valid Router-owned graph | Router-local result | Router-local report | Router-local advisory gate |
| Native Goal | `verified-host-scheduler` | `verified-event-store` + `activation-receipt-verifier` | `verified-evidence-store` + `gate-authority` |
| Missing graph | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally |
| Corrupt graph | Sanitized `internal-error` | Sanitized `internal-error` | Sanitized `internal-error` |

<a id="failure-modes"></a>
## Failure modes

- A large request forced into `single` loses phase-specific capability and evidence checks.
- A copy edit forced into `managed-goal` creates needless state and consent overhead.
- Reusing one route across phases keeps stale capabilities active after the work changes.
- In `v2.0.2`, `v2.1.0`, `v2.1.1`, and development main, Native Goal work uses each tool's verified Host capability and does not mutate native Codex Goal.
- A missing Router-owned graph requests local graph creation or replay; it does not switch to an invented Host path.
- A corrupt graph returns a sanitized `internal-error`; corruption details stay in internal diagnostics.
- A passing Router-local gate is only advisory. It does not activate a Skill, authorize a native Goal transition, or grant deployment or production permission.
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
