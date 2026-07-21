---
title: Build a verified Host adapter
description: Connect Host-owned authority to the Router without exposing executable or secret inputs to the model.
---

The integration kit gives Host implementers one vendor-neutral contract. The
included adapter is labeled `reference-not-production-authority`: it is **not
production** authority, not a real Host pilot, and not proof of `hybrid-full`.

## Keep authority server-owned

Create trusted resources inside the Host, then pass the adapter to
`composition.open`. Never accept executable paths, database or artifact
locations, environment variables, secrets, or receipt authority from model or
MCP arguments.

## Implement the manifest

Declare an owner, trusted input or receipt, freshness rule, fail closed
behavior, and public-safe diagnostic for each boundary:

- runtime authority and runtime context;
- scheduler and native Goal resume refresh;
- capability snapshot and policy snapshot;
- route validation, activation preflight, and receipt verification;
- append-only event coordination with CAS and idempotency;
- evidence context, gate evaluation, and gate persistence;
- artifact protection; and
- evaluation authorization.

If any authority is missing, stale, forged, or bound to the wrong session, fail
closed before mutation. Public output should identify the safe reason code,
never the trusted value.

## Prove development conformance

Run the reference adapter from a repository checkout:

```powershell
$env:PYTHONPATH = (Resolve-Path 'packages/router-core/src').Path
python examples/reference-host-adapter/reference_host.py
```

A passing report covers composition, stale snapshot, forged receipt, wrong
session, CAS conflict, idempotent replay, native Goal resume refresh, and
artifact protection failure. Then replace the in-memory ports with Host-owned
implementations and run the same suite in CI.

The runner probes the same `RouterCompositionPorts` returned to
`composition.open`; probe inputs cannot replace them with shadow ports. A
manifest authority flag is only declared metadata, so development conformance
always reports `production_authority_verified=false`.

Conformance is an engineering gate, not deployment attestation. Complete a
separate real Host pilot before describing the integration as production-ready
or `hybrid-full`.
