---
title: Adopt V2 in an existing team
description: Introduce runtime-aware routing without replacing Host authority or forcing every request through a Goal.
---

## Start with an operating boundary

Workflow Skill Router selects a routing envelope and the smallest justified SKILL set. It does not grant tool access, approve side effects, replace Codex Goal state, or make an installed capability available. Keep Host permissions, approvals, and deployment controls authoritative.

## Choose the rollout surface

| Environment | Start with | Upgrade when |
| --- | --- | --- |
| Plugin/MCP supported | Plugin + MCP | A verified Host integration is ready |
| Instructions only | Skill-only fallback | Plugin support becomes available |
| Existing V1 router | Side-by-side V2 tasks | Representative routes pass review |

Do not identify Skill-only as `hybrid-full`. It is an intentional fallback with a smaller assurance boundary.

## Build an evidence-backed inventory

Discover capabilities at runtime, then merge observations by authority. Separate installation, Host exposure, authorization, policy eligibility, freshness, and risk. A local file or cached observation is not proof that a tool can run now.

## Calibrate the three envelopes

- Use `single` for bounded work that can be completed and verified in one pass.
- Use `phased` when the task crosses distinct stages or verification boundaries.
- Use `managed-goal` for resumable dependency graphs, durable progress, and explicit completion criteria.

Large wording does not automatically require a Goal. Complexity, dependencies, resume needs, and state transitions decide the envelope.

## Preserve user choice

When the user names no SKILL, auto-route the minimal set without a consent ceremony. When the user explicitly names a SKILL, lock that selection. Any proposed support outside the lock stays inactive until the user accepts it.

Declare expected SKILL usage before work. At completion, disclose what was actually used, skipped, or added with consent.

## Pilot and expand

Run a small suite covering automatic single routing, phased work, explicit lock acceptance/rejection, Managed Goal degradation, and unavailable capabilities. Review the Flight Recorder evidence shape, then add team-specific policies only where observed failures justify them.

Next: [V1 migration](/Workflow-skill-router/guides/migrate-v1-to-v2/) and [security boundaries](/Workflow-skill-router/reference/security-boundaries/).
