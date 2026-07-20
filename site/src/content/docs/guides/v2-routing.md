---
title: V2 routing and Goal orchestration
description: Single, Phased, Managed Goal, Explicit Skill Lock, and consent.
---

# V2 routing

## Bring your own Skill Tree

When the current request does not name a SKILL, `plan_work` can apply a Personal Routing Profile. The strict JSON contract maps objective keywords, domains, tags, and work modes to a phased Skill Tree. Workspace rules outrank personal rules; the Router selects one complete tree rather than deep-merging both.

Profile output is `intended-unverified`. Runtime Capability Discovery still gates activation, and an explicit user SKILL always overrides Profile preferences. Use `profile preview` before relying on a new rule. Skill-only applies the same policy as advisory `skill-only-fallback` and needs Host filesystem access to load fixed local Profile files. Personal Routing Profiles ship in `v2.0.0-beta.2`.

The Router classifies Goal relation before task size. It then chooses **Single**, **Phased**, or **Managed Goal**. Every Phase and Goal Work Item is routed independently.

When the user does not name a SKILL, the Router auto-selects the smallest useful Primary and Supporting set without asking for consent on its own recommendations. Explicit Skill Lock remains active across all three envelopes only when the user names a SKILL; support outside that set is proposed with purpose and scope and is never opened before consent.

The Router declares planned SKILLs before execution and reports actual SKILLs after completion. `skill-only-fallback` is honest about missing durable guarantees; the Plugin's persistent local R0 control plane can run `plan_work`, while `hybrid-full` still requires verified preflight. R2/R3 remains blocked on host approval.

The 80 fixtures are **Tier 0 Contract**. A real Behavior run without an adapter is `manual-required`.
