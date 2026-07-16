---
title: Explicit Skill Lock
description: Preserve user-selected SKILLs without prompting on every automatic route.
---

<a id="problem"></a>
## Problem

Users need their named SKILLs respected, but asking for consent on every Router-selected support capability makes normal work unusable. Silent substitutions are worse: they violate the user's instruction and hide context cost.

<a id="contract"></a>
## Contract

When no SKILL is named, selection mode is `auto`; the Router chooses minimal support without asking permission for its own recommendation. When the user names one or more SKILLs, selection mode is `explicit-locked`:

- `use`: prefer the named SKILL as primary; outside support needs consent.
- `only`: the named set is the full allowed set; outside support is forbidden.
- `all`: every named SKILL must be activated or explicitly waived before completion.

<a id="example"></a>
## State, input, and output example

```json
{
  "input": {"explicit_skill_ids": ["skill:api-designer"], "semantics": "use"},
  "proposal": {"support": "skill:qa-test-planner", "scope": "verify contract"},
  "user_decision": "reject",
  "active_selections": ["skill:api-designer"]
}
```

<a id="failure-modes"></a>
## Failure modes

- Rejected support appears in the audit trail but never in activation events.
- The same rejected proposal cannot be asked again after a cosmetic phase-ID change.
- If the requested SKILL cannot complete mandatory work, the Router narrows the outcome or reports a block; it does not substitute silently.

<a id="security-boundary"></a>
## Security and authority boundary

SKILL consent authorizes instruction activation for a declared scope. It does not authorize Plugin installation, file writes, deployment, messages, secrets, or production access. Host permission remains authoritative for R2/R3 actions.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_explicit_lock tests.routing.test_consent -v
```
