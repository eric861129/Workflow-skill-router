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

Expected: the named SKILL remains active; proposed outside support requires consent and stays inactive after rejection.

Managed Goal:

```text
Continue the migration Goal across API, Web, and docs.
```

Expected local behavior: `plan_work` succeeds, `get_next_work` returns typed `capability-unavailable`, and `get_router_status` remains readable. A verified Host integration is required for actual scheduling.

## 4. Inspect the evidence

Open the homepage Flight Recorder. Expand each MCP step to inspect sanitized request/response JSON. `runtime-trace` is bundled local evidence; `fixture-trace` proves the Host contract through test ports and is not a live Host connection.

## Next steps

- [Runtime Capability Discovery](/Workflow-skill-router/concepts/runtime-capability-discovery/)
- [Routing Envelopes](/Workflow-skill-router/concepts/routing-envelopes/)
- [MCP tool reference](/Workflow-skill-router/reference/mcp-tools/)
- [Troubleshooting](/Workflow-skill-router/guides/troubleshooting/)
