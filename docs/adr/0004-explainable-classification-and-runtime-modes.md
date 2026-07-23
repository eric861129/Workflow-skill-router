# ADR 0004: Explainable classification and runtime modes

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

### Semantic recommender decision gate

The default decision is
`deterministic-default-no-semantic-recommender`. Deterministic Profiles,
aliases, linting, and `profile preview --explain` remain the supported route.
No Pilot data means the gate is unmet, not a negative performance claim about
semantic routing.

An experimental semantic recommender proposal may be reviewed only after real
Pilot data proves all three conditions:

1. `>=10%` of eligible manual envelope corrections are attributable to lexical
   synonym misses;
2. `profile preview --explain` rules out deterministic configuration causes;
3. a server-configured advisory-only adapter exists and cannot activate a
   Skill, persist a route, or grant authority.

Meeting the gate authorizes a proposal review only. It does not authorize
implementation, model quota, route mutation, a Host Pilot, or release.

### Authority modes

Router-owned local state and Host-authoritative state use distinct `authority_mode` values:

- `router-local` means a result applies only to Router-owned state. Published beta.3 covers planning, consent, and status; the prepared GA candidate also implements bounded local scheduling, reported progress, and advisory gates with `host_transition_authorized=false`.
- `verified-host` means the Host supplied the required authoritative state, receipts, policy, and transition capability.
- `configured-adapter` means a server-configured evaluation adapter and its authorization govern the operation.

`conditional-local` is an availability class, not an authority upgrade. A conditionally local operation must fail closed when the target is a native Goal, formal evidence, Skill activation, or another Host-owned transition.

### Runtime readiness

#### Published beta.3 (`published-beta.3`)

| Current class | Tools | Boundary |
| --- | --- | --- |
| `local-ready` (4) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Bundled R0 supports only their documented Router-local scope. |
| `verified-host` (5) | `sync_runtime_context`, `get_next_work`, `validate_route`, `record_work_event`, `evaluate_gate` | Requires Host-owned authority, current state, and receipts. |
| `configured-adapter` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Requires a configured evaluation adapter, authorization, and applicable attestation. |

#### Prepared GA candidate (`prepared-ga-candidate`)

This candidate implements the `conditional-local` work, but it is **not included in published beta.3** and is not a released GA version. Its lifecycle remains `prepared-local-candidate`; a later trusted metadata-only promotion must bind `release_source_revision` to this exact reviewed GA candidate SHA before dispatch.

| Source class | Tools | Boundary |
| --- | --- | --- |
| `local-ready` (4) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Unchanged Router-local R0 operations. |
| `conditional-local` (3) | `get_next_work`, `record_work_event`, `evaluate_gate` | Router-owned graphs and local advisory evidence only; results use `authority_mode=router-local` and `host_transition_authorized=false`. |
| `verified-host` (2) | `sync_runtime_context`, `validate_route` | Host authority remains mandatory. |
| `configured-adapter` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Configured-adapter authority remains mandatory. |

GA is not defined as all 12 tools being locally usable. Implementing three conditional-local source paths must not weaken verified-Host or configured-adapter authority to improve a tool-count metric.

| Condition | `get_next_work` | `record_work_event` | `evaluate_gate` |
| --- | --- | --- | --- |
| Valid Router-owned graph | Router-local result | Router-local report | Router-local advisory gate |
| Native Goal | `verified-host-scheduler` | `verified-event-store` + `activation-receipt-verifier` | `verified-evidence-store` + `gate-authority` |
| Missing graph | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally |
| Corrupt graph | Sanitized `internal-error` | Sanitized `internal-error` | Sanitized `internal-error` |

## Fail-closed behavior

- If a local request targets native Goal progress or steer, the Router returns a Host requirement and does not mutate Goal state.
- Published beta.3 keeps `get_next_work`, `record_work_event`, and `evaluate_gate` on the verified-Host path.
- In the unreleased source checkout, missing graphs request local creation or replay, while corrupt graphs return a sanitized `internal-error`; neither condition invents Host authority.
- If a Router-local gate passes, it proves only the local advisory gate; it does not claim Skill activation or grant deployment or production permission.
- If a semantic adapter proposes a different envelope, the candidate remains advisory and cannot replace the persisted route.
- If the required Host receipt, configured adapter, consent, or Explicit Skill Lock condition is absent, the protected operation does not run.

## Consequences

Routing decisions become explainable and replayable without confusing classification with authorization. Local workflows gain useful, bounded operations while native Goal state, Skill activation, protected tools, formal evidence, and production effects remain under their existing authorities.
