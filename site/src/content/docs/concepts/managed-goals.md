---
title: Managed Goals
description: Coordinate large work while keeping the native Codex Goal host-owned.
---

<a id="problem"></a>
## Problem

Large goals span many tasks, repositories, and sessions. A flat checklist loses dependency order and resume context; a Plugin that mutates the native Goal directly would cross the host authority boundary.

<a id="contract"></a>
## Contract

Managed Goal planning creates a dependency Work Graph. Each Work Item has its own `single` or `phased` envelope and routing decision. Resume requires fresh Goal, workspace, capability, and evidence context before the scheduler returns more work.

The Router can emit `complete` or `blocked` status candidates. Codex owns the actual Goal state transition. A blocked candidate needs three countable turns with the same blocker and no runnable required item.

Published beta.3 exposes 4 always local-ready tools and keeps 5 tools on the verified-Host path. The **unreleased beta.5 source checkout**, which is **not included in published beta.3**, exposes **4 always local-ready + 3 Router-owned conditional-local** tools. For a validated Router-owned graph with no Native Goal authority, `get_next_work`, reported progress, and an advisory local gate can complete the Router-local loop. This is not `7/12 local-ready`: Explicit Skill Lock and consent are unchanged, and a local gate pass does not prove Skill activation, Host evidence, deployment, or production approval.

Native Goal scheduling requires `verified-host-scheduler`; its formal progress path requires `verified-event-store` plus `activation-receipt-verifier`; its gate path requires `verified-evidence-store` plus `gate-authority`. A missing graph requests local creation or replay through `router-owned-work-graph`. A corrupt graph returns a sanitized `internal-error`, not a fabricated Host fallback. Every unavailable or unsafe branch must **fail closed**.

<a id="example"></a>
## State, input, and output example

```json
{
  "goal_binding_id": "goal:host-42",
  "work_graph": [
    {"id": "api-contract", "depends_on": []},
    {"id": "web-delivery", "depends_on": ["api-contract"]},
    {"id": "docs-handoff", "depends_on": ["web-delivery"]}
  ],
  "host_goal_mutated": false
}
```

<a id="failure-modes"></a>
## Failure modes

- Cycles and overlapping ready write scopes are rejected.
- Status questions do not increment semantic revision.
- Completed items survive a Goal edit; unstarted items may be replaced.
- Router-owned graphs can return a Router-local next item; Native Goal scheduling reports `capability-unavailable` and never fakes Host authority.

<a id="security-boundary"></a>
## Security and authority boundary

Goal bindings require host identity. Status candidates carry evidence digests and never self-apply. Repository access, deployment, communication, and external side effects remain governed by the Codex host.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.goals.test_goal_orchestrator tests.goals.test_candidates -v
```
