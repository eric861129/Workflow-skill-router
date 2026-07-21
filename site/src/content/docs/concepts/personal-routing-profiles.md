---
title: Personal Routing Profiles
description: Own the Skill Tree while Runtime Capability Discovery keeps activation honest.
---

A Personal Routing Profile turns your preferred engineering workflow into deterministic routing data. It preserves V1's user-owned Skill Tree without bringing back a static catalog that pretends every SKILL is available.

This contract is part of `v2.0.0-beta.2`. The 36-attempt Model Evaluation published for beta.1 does not cover Personal Routing Profiles; this feature currently has deterministic contract, integration, security, and package evidence only.

## What you control

Each rule matches objective keywords, domains, tags, or work modes. Its route selects `single`, `phased`, or `managed-goal`, then defines each Phase with exactly one Primary SKILL, no more than three immediate support SKILLs, and one exit gate ID.

```json
{
  "schema_id": "workflow-skill-router/routing-profile",
  "schema_version": "1.0.0",
  "artifact_kind": "routing-profile",
  "profile_id": "personal:api-delivery",
  "scope": "personal",
  "enabled": true,
  "rules": [{
    "rule_id": "api-delivery",
    "priority": 100,
    "match": {
      "objective_keywords": ["api", "應用程式介面", "openapi"],
      "domains": ["api"],
      "tags": [],
      "work_modes": []
    },
    "route": {
      "work_mode": "phased",
      "skill_tree": [{
        "phase_id": "contract",
        "primary_skill_id": "skill:api-designer",
        "support_skill_ids": ["skill:api-guidelines-skill"],
        "exit_gate": "contract-reviewed"
      }]
    }
  }]
}
```

The standalone package includes complete three-Phase examples at `assets/personal-routing-profile.example.json` and `assets/workspace-routing-profile.example.json`.

## Precedence without surprise merges

The effective order is:

1. System, developer, safety, and Host hard constraints.
2. A SKILL explicitly named by the user for the current request.
3. Workspace Profile.
4. Personal Profile.
5. Built-in routing.

The short form is `workspace > personal > built-in`, but the current user's explicit choice always sits above all Profiles. If workspace and personal rules both match, the Router takes the complete workspace tree. It never deep-merges two trees into a route the user did not define.

## Install and preview

Put a workspace Profile at `.codex/workflow-skill-router.json`. Use `assets/workspace-routing-profile.example.json`, whose identity fields are:

```json
{
  "profile_id": "workspace:api-delivery",
  "scope": "workspace"
}
```

Do not copy the personal example unchanged: a workspace file with `scope: personal` fails closed. Install personal profiles into the external Router data directory:

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api --explain
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile lint .\my-profile.json
```

`plan_work` accepts an optional `routing_context` with `workspace_root`, `domains`, `tags`, and `current_phase_id`. Existing beta.1 calls can omit it. Only the current Phase Primary and immediate support become `planned_skill_ids`; the full tree remains visible as planning data.

In MCP mode, `workspace_root` must be inside a root advertised by the Client or explicitly configured by the operator through `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`. If exactly one Client root exists, the Plugin binds it for a legacy caller that omitted `routing_context`. Multiple roots require an explicit matching root. A model-supplied arbitrary local path returns `workspace-root-untrusted` and is never opened.

## Explain and lint deterministic rules

Add `--explain` to `profile preview` to receive one stable trace for every candidate rule in enabled Profiles. Each record contains only the rule ID, match result, matched and unmatched dimensions, and reason codes. It never echoes the full objective, a local absolute path, or a SKILL instruction body. Explain is observability for the existing matcher; it does not grant authority or execute Profile content.

Run `profile lint <path>` before installing a Profile. It reports duplicate or permanently shadowed rules, conflicts with equal priority and specificity, and a Primary SKILL repeated as support. For a phased route, add `--current-phase <phase-id>` to verify that the current Phase exists in every applicable phased tree. Errors exit with code `2`; advisory-only results exit with code `0`.

Matching remains schema `1.0.0` deterministic lexical matching. There is no embedding, executable matcher, semantic retrieval, or implicit alias expansion. To match both `API` and `應用程式介面`, list both strings in `objective_keywords`. The linter may advise that a common alias is missing, but never edits or expands the rule.

## Runtime Capability Discovery still decides activation

A Profile match returns `intended-unverified`. Runtime Capability Discovery still checks presence, exposure, compatibility, authentication, policy eligibility, and freshness. An unavailable intended SKILL remains the intended SKILL and receives an honest limitation; the Router does not silently replace it.

Profiles contain data, not instructions. The strict contract rejects unknown fields such as `instructions`, executable paths, shell content, permissions, and arbitrary agent directives. Invalid existing profiles fail closed instead of disappearing from the decision trace.

## Plugin + MCP and Skill-only

Plugin + MCP loads, validates, resolves, persists, and previews the Profile deterministically. It stores personal profiles outside the Plugin cache.

Skill-only can read the same fixed workspace and personal locations only when the Host grants filesystem access to them; otherwise the Profile content must be supplied in the conversation. Its result is advisory `skill-only-fallback`. It cannot claim durable loading, compare-and-swap, drift detection, or enforced activation. Both modes preserve Explicit Skill Lock: once the user names a SKILL in the current request, Profile support disappears and any additional support requires scoped consent.
