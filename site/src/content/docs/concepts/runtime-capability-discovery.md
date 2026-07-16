---
title: Runtime Capability Discovery
description: Decide whether a capability is truly usable before routing work to it.
---

<a id="problem"></a>
## Problem

An installed SKILL or registered tool is not automatically usable. The host may hide it, authentication may be missing, its schema may have changed, policy may forbid it, or the observation may be stale.

<a id="contract"></a>
## Contract

Discovery merges filesystem metadata, Plugin handshake data, agent observations, cache hints, and verified host evidence. Each capability records source-qualified identity, provenance, compatibility, authentication, freshness, content identity, and availability for risks R0–R3. Host evidence outranks agent and cache claims; cache data can never promote an unavailable capability.

<a id="example"></a>
## State, input, and output example

```json
{
  "input": {"capability_id": "skill:playwright", "host_exposed": true, "authenticated": true},
  "output": {
    "availability_by_risk": {"R0": "available", "R1": "available", "R2": "approval-required", "R3": "unavailable"},
    "freshness": "fresh",
    "provenance": ["plugin-handshake", "verified-host"]
  }
}
```

The snapshot ID changes when authoritative availability, schema, trusted content identity, or freshness identity changes.

<a id="failure-modes"></a>
## Failure modes

- A provider timeout produces explicit degraded evidence; the provider is not silently omitted.
- Unknown authoritative fields fail closed.
- Filesystem metadata cannot claim host authorization.
- A stale snapshot cannot authorize protected R2/R3 work.

<a id="security-boundary"></a>
## Security and authority boundary

The agent may report what it observes, but only the host can attest exposure, authentication, approval, and policy authority. Discovery opens SKILL instruction bodies only through the bound-content activation path; listing metadata does not activate a capability.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.capabilities.test_runtime_context tests.capabilities.test_merge -v
```
