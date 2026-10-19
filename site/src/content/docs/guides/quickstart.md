---
title: V2 Quickstart
description: Choose Plugin + MCP or Skill-only, verify the runtime label, and inspect one route.
---

## 1. Choose the runtime

Install [Plugin + MCP](/Workflow-skill-router/guides/install-plugin/) when Codex supports it. Install [Skill-only](/Workflow-skill-router/guides/install-skill/) for instruction-only fallback. Do not install both under the same identity unless you are deliberately testing precedence.

## 2. Verify the label

Plugin checkout:

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

Expected: `runtime_profile` is `bundled-local-r0`; `plan_work`, `propose_support_consent`, `transition_support_consent`, and `get_router_status` are local-ready. Skill-only tasks must state `skill-only-fallback`.

## 3. Try three requests

Small auto route:

```text
Document one API error response.
```

Expected envelope: `single`. No support-consent prompt appears because the user named no SKILL.

Explicit Skill Lock:

```text
Use api-designer only. Do not add support without asking.
```

Expected: the named SKILL remains the primary planned selection; proposed outside support requires consent and stays out of the plan after rejection. A plan alone does not prove actual Skill activation.

Managed Goal:

```text
Continue the migration Goal across API, Web, and docs.
```

Expected local behavior depends on the work graph. With a valid Router-owned graph, `get_next_work` can return the next local Work Item with `authority_mode=router-local` and `host_goal_mutated=false`. Scheduling for a bound Native Goal requires verified Host capabilities; without them, the tool returns typed `capability-unavailable`. `get_router_status` remains readable. A local plan or next step does not prove Skill activation or authorize deployment.

## 4. Try a Personal Routing Profile

Personal Routing Profiles ship in `v2.0.0-beta.2`. From a contributor checkout, try a user-owned Skill Tree:

```powershell
Copy-Item starter/v2/workflow-skill-router/assets/personal-routing-profile.example.json ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api
```

Use `.codex/workflow-skill-router.json` for a workspace Profile. The preview must report `intended-unverified`; Runtime Capability Discovery still controls activation. Skill-only can interpret the same contract only as `skill-only-fallback`.

## 5. Inspect the evidence

Open the homepage Flight Recorder. Expand each MCP step to inspect sanitized request/response JSON. `runtime-trace` is bundled local evidence; `fixture-trace` proves the Host contract through test ports and is not a live Host connection.

## Next steps

- [Runtime Capability Discovery](/Workflow-skill-router/concepts/runtime-capability-discovery/)
- [Routing Envelopes](/Workflow-skill-router/concepts/routing-envelopes/)
- [Personal Routing Profiles](/Workflow-skill-router/concepts/personal-routing-profiles/)
- [MCP tool reference](/Workflow-skill-router/reference/mcp-tools/)
- [Troubleshooting](/Workflow-skill-router/guides/troubleshooting/)
