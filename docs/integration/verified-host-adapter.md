# Verified Host Integration Kit

The Host Integration Kit is a vendor-neutral development contract for wiring
Host authority into Workflow Skill Router through `composition.open`. The
included reference uses `reference-not-production-authority`; it is **not
production** authority, is not a Host pilot, and does not establish
`hybrid-full`.

## Security boundary

The Host constructs `ServerOwnedHostResources` and the adapter constructs
`RouterCompositionPorts`. A model or MCP caller may request an operation, but
cannot select an executable path, database, artifact location, environment
variable, secret, signing key, or receipt authority. Missing or stale authority
must fail closed with a public-safe diagnostic and no state change.

## Required manifest

Every row must declare the port/capability owner, trusted input or required
receipt, freshness rule, fail closed behavior, and public-safe diagnostic.

| Port | Responsibility and evidence |
| --- | --- |
| runtime authority | Bind the current session to Host authority and a runtime authority receipt. |
| runtime context | Supply a fresh, Host-verified runtime context and snapshot identity. |
| scheduler | Select current work only after native Goal resume context is refreshed. |
| snapshot repository | Reject a stale capability snapshot using risk-specific freshness. |
| policy repository | Require the current policy snapshot and policy receipt. |
| route validation | Validate a route against current snapshot, policy, and Host context. |
| activation preflight | Issue a single-use activation lease after validation. |
| activation receipt verification | Reject forged, reused, or wrong-session receipt data. |
| append-only event coordination | Preserve CAS, idempotency, and append-only event identity. |
| gate context | Resolve current evidence without trusting caller-supplied evidence. |
| gate evaluator | Evaluate the gate under current Host authority. |
| gate coordinator | Persist the gate result with append-only and CAS guarantees. |
| artifact protection | Protect bytes before persisting or revealing an artifact reference. |
| evaluation | Require a configured evaluation adapter and sealed authorization. |

## Conformance workflow

1. Implement `HostIntegrationAdapterPort`.
2. Return a complete, server-owned `HostIntegrationManifest`.
3. Build every port through `RouterCompositionPorts`; do not create a parallel
   service root.
4. Run `run_host_conformance(adapter, resources)` in CI.
5. Review only sanitized public evidence outside the trusted Host boundary.
6. Complete a separate real Host pilot before making production or
   `hybrid-full` claims.

The development suite checks happy composition, stale snapshot, forged
activation receipt, wrong session, CAS conflict, idempotent replay, native Goal
resume refresh, and artifact protection failure. It intentionally does not
exercise a vendor Host, external state, or a live evaluation model.
