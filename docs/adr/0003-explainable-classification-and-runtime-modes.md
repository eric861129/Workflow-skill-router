# ADR 0003: Explainable classification and runtime modes

- Status: Accepted
- Date: 2026-07-21

## Context

The Router needs to choose a useful execution envelope without implying that it understands every task semantically. It also needs to expose more Router-owned operations locally without weakening Explicit Skill Lock, consent, verified-Host authority, or configured-adapter authority.

Envelope selection and runtime authorization are separate decisions. A structural classification can recommend `single`, `phased`, or `managed-goal`; it cannot activate a Skill, grant a tool, mutate native Codex Goal state, or approve a deployment or production side effect.

## Decision

### Classification order and provenance

Classification happens before execution work:

1. Classify Goal status requests and side questions as control/read-only requests, not new execution work.
2. Native Goal progress or steer determines the outer `managed-goal` envelope. Router-local state may describe a candidate but never mutates native Codex Goal.
3. For a detached request or the current Managed Goal work item, choose the inner envelope in this order: explicit `requested_work_mode`, the deterministic structural analyzer, a deterministic Profile route, then the conservative builtin fallback.

Every result records `classification_source` and `classification_reason_codes`. Analyzer-derived results also record `classifier_revision: deterministic-objective-v1`; confidence is categorical rather than a fabricated precision score. The analyzer only evaluates bounded structural signals such as stages, dependencies, resumability, and repository scope. It does not claim universal semantic understanding.

Profiles remain deterministic. A semantic adapter may return a reviewable candidate, but it cannot directly rewrite a persisted route. Persisting a route requires the normal deterministic policy, Explicit Skill Lock, consent, capability, and authority checks.

### Authority modes

Router-owned local state and Host-authoritative state use distinct `authority_mode` values:

- `router-local` means a result applies only to the Router-owned work graph or local advisory evidence. Local transition and gate results set `host_transition_authorized=false`.
- `verified-host` means the Host supplied the required authoritative state, receipts, policy, and transition capability.
- `configured-adapter` means a server-configured evaluation adapter and its authorization govern the operation.

`conditional-local` is an availability class, not an authority upgrade. A conditionally local operation must fail closed when the target is a native Goal, formal evidence, Skill activation, or another Host-owned transition.

### Runtime readiness

| Readiness | Operations | Boundary |
| --- | --- | --- |
| `local-ready` | `plan_work`, consent proposal/transition, `get_router_status` | Four bundled R0 operations are always available for their documented Router-local scope. |
| `conditional-local` | `get_next_work`, `record_work_event`, `evaluate_gate` | Available only for a Router-owned graph and local advisory evidence; `authority_mode=router-local` and `host_transition_authorized=false`. |
| `verified-host-required` | `sync_runtime_context`, `validate_route` | Requires Host-owned authority, current state, and receipts. |
| `configured-adapter-required` | model evaluation, comparison, export | Requires a configured evaluation adapter, authorization, and applicable attestation. |

GA is not defined as all 12 tools being locally usable. The honest readiness statement is four always `local-ready`, three Router-owned `conditional-local`, and five operations that retain verified-Host or configured-adapter boundaries.

## Fail-closed behavior

- If a local request targets native Goal progress or steer, the Router returns a Host requirement and does not mutate Goal state.
- If a Router-local gate passes, it proves only the local advisory gate; it does not claim Skill activation or grant deployment or production permission.
- If a semantic adapter proposes a different envelope, the candidate remains advisory and cannot replace the persisted route.
- If the required Host receipt, configured adapter, consent, or Explicit Skill Lock condition is absent, the protected operation does not run.

## Consequences

Routing decisions become explainable and replayable without confusing classification with authorization. Local workflows gain useful, bounded operations while native Goal state, Skill activation, protected tools, formal evidence, and production effects remain under their existing authorities.
