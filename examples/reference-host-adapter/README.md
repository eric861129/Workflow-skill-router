# Reference Host adapter

This vendor-neutral example shows how a Host can inject verified ports through
`composition.open`. Its authority label is
`reference-not-production-authority`: it is **not production** authority, not a
real Host pilot, and never proves `hybrid-full`.

## What the contract covers

The manifest declares an owner, trusted input or receipt, freshness rule,
fail closed behavior, and public-safe diagnostic for every boundary:

- runtime authority and runtime context;
- scheduler and native Goal resume refresh;
- capability snapshot and policy snapshot;
- route validation, activation preflight, and receipt verification;
- append-only event coordination with CAS and idempotent replay;
- evidence context, gate evaluation, and gate persistence;
- artifact protection; and
- evaluation authorization.

Database paths, artifact locations, executable paths, environment variables,
secrets, and receipt authority remain server-owned. They are never accepted
from a model or MCP request.

## Run the development conformance suite

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path 'packages/router-core/src').Path
python examples/reference-host-adapter/reference_host.py
```

The JSON result contains only public-safe diagnostics. A passing result means
the adapter satisfies the development conformance contract for stale snapshot,
forged receipt, wrong session, CAS conflict, idempotent replay, native Goal
resume refresh, and artifact protection failure. It does not certify a real
Host deployment or `hybrid-full`.

For a production adapter, replace every in-memory port with a Host-owned
implementation, keep the same `RouterCompositionPorts` composition boundary,
run the suite, and then complete a separate real-environment pilot.
