---
title: Migrate from V1 to V2
description: Move from a static template router to the V2 Plugin or Skill-only contract with a reversible rollout.
---

## What changes

| V1 | V2 |
| --- | --- |
| Static skill tree and route templates | Runtime Capability Discovery plus typed routing contracts |
| One route for the whole request | Single, Phased, or Managed Goal envelopes |
| Broad support lists | Minimal selection and Explicit Skill Lock |
| Validator-centric proof | Contract, runtime trace, Behavior, and Outcome evidence classes |
| Local files imply availability | Host exposure, auth, policy, freshness, and risk remain separate |

## 1. Inventory your V1 custom rules

Record routes, conflict rules, explicit user-choice behavior, and any internal capability names. Do not copy the public V1 Template Catalog into V2; keep only rules that reflect your environment.

## 2. Choose an install mode

Use [Plugin + MCP](/Workflow-skill-router/guides/install-plugin/) when available. Use [Skill-only](/Workflow-skill-router/guides/install-skill/) when the Host cannot load the Plugin. Keep the V1 installation intact until V2 routing is verified in new tasks.

## 3. Translate policies

Move V1 Skill Tree preferences into a Personal Routing Profile instead of flattening them into one global prompt. Convert each workflow matcher into a rule and each stage into a `skill_tree` Phase with one Primary, at most three immediate support SKILLs, and an exit gate ID.

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\migrated-v1-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\migrated-v1-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Representative V1 task" --work-mode phased
```

These Personal Routing Profile commands ship in `v2.0.0-beta.2`; contributor checkouts use the longer repository-relative runtime path shown below.

Use `scope: workspace` at `.codex/workflow-skill-router.json` for project policy and `scope: personal` for cross-project preferences. Workspace wins as one complete route; it does not deep-merge with personal. Runtime Capability Discovery still marks every selected SKILL `intended-unverified` until activation is proven.

- Convert small routes to `single`.
- Split multi-stage routes into `phased` and define a verification gate per phase.
- Convert resumable dependency work into `managed-goal` Work Items.
- Map “use only X” and “use all named SKILLs” to Explicit Skill Lock semantics.
- Replace inferred availability with Runtime Capability Discovery evidence.

## 4. Verify side by side

Run representative small, phased, explicit-lock, and Goal scenarios. Compare planned SKILLs, rejected support, capability-unavailable results, and final usage disclosure. Use the public Flight Recorder as the expected evidence shape, not as production Host proof.

## 5. Roll back safely

If V2 blocks required work, disable the V2 Plugin or move the standalone V2 SKILL out of the active Skills directory, then restore the known V1 configuration. Immutable V1 source and packages remain available from the [`v1.3.1` tag](https://github.com/eric861129/Workflow-skill-router/tree/v1.3.1) and GitHub Release.

V1 files will leave the V2 primary branch only after the reviewed removal manifest and manual cleanup gate. Git history is not the migration plan; the immutable tag is the recovery source.
