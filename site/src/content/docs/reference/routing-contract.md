---
title: V2 routing contract
description: The inspectable decision and disclosure contract for every routed unit of work.
---

# V2 routing contract

The Router creates a bounded decision for the current unit of work. It does not turn Skill selection into permission, silently mutate a native Codex Goal, or claim runtime capabilities that the host did not verify.

## 1. Profile the request

Resolve the Goal relation first, then select exactly one envelope:

- **Single** — one bounded intent with one minimal Primary capability.
- **Phased** — two or more distinct stages; each Phase receives a fresh route from current evidence.
- **Managed Goal** — resumable work with milestones or dependencies; every Work Item is routed as Single or Phased.

The result records the envelope, runtime mode, risk, scope anchor, and current capability snapshot.

## 2. Lock user authority

When there is no User-specified Skill, selection mode is `auto`: choose the smallest sufficient Primary and Supporting set without asking for consent to the Router's own recommendation.

When a User-specified Skill exists, selection mode is `explicit-locked`. The named Skill remains authoritative. Additional support requires a scoped proposal and consent; declined support remains rejected and must not be activated or repeatedly proposed in the same scope.

In `auto` mode, inspect capability descriptions, domains, stages, and availability instead of guessing from names. The Primary owns the current decision bottleneck or first unfinished Phase. Supporting Skills are limited to capabilities indispensable to the current Phase and its immediate exit gate; later-Phase capabilities are deferred and rerouted when that Phase begins. A Managed Goal chooses the capability needed by the current Work Item rather than defaulting to the Router itself. Skills for future Work Items stay in the plan and are routed when that Work Item begins; they are never aggregated into the current support set. Availability gates activation after semantic selection and never silently rewrites the intended Skill.

Use the deterministic shape `current route = current Phase Primary + immediate exit-gate support`. A Phase transition creates a new route. During Goal planning, future delivery Skills stay in the Work Graph. When a verified snapshot marks an intended canonical Skill unavailable, that Skill remains Primary; fallback details belong in the limitation, never in `support_skills`.

## 3. Declare the plan

Before execution, disclose:

```text
Envelope: single | phased | managed-goal
Phase or Work Item: current bounded scope
Runtime mode: hybrid | skill-only
Planned Skills: Primary plus approved Supporting Skills
Consent: not-required | pending | granted | declined
Fallback or exit gate: explicit when capability is unavailable
```

`plan_work` exposes the corresponding `routing_envelope`, `selection_mode`, `support_consent_required`, `planned_skill_ids`, and `runtime_mode` fields.

## 4. Validate before activation

A route is executable only when capability identity, freshness, authority, policy revision, consent grants, risk requirements, and activation bindings pass. Runtime permission and production authorization remain separate from Skill consent.

Unavailable capabilities return a typed limitation and fallback. They are never represented as successful execution.

## 5. Report actual use

After the unit completes or stops, disclose:

```text
Actual Skills: capabilities whose instructions or runtime bindings were opened
Changed from plan: additions, omissions, and why
Outcome: complete | limited | blocked
Evidence: route, activation, gate, or fallback references
```

The Actual list must not include a Skill merely because it was discovered, recommended, or present in metadata.

See the [V2 routing guide](../guides/v2-routing.md) and [security boundaries](./security-boundaries.md) for orchestration and authority details.
