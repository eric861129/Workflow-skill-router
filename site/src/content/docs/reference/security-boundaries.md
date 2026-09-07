---
title: Security Boundaries
description: Separate instruction consent, runtime authority, side effects, and evaluation trust.
---

## Four separate decisions

1. **Install:** place a Plugin or SKILL where Codex can discover it.
2. **Activate instructions:** consent to read/use a SKILL for a declared scope.
3. **Authorize runtime:** allow tools, files, network, subprocesses, or secrets through the Host.
4. **Authorize side effects:** approve deployment, messages, production changes, publication, or other consequential actions.

One decision never implies the next.

## Fail-closed rules

- Agent observations cannot mint Host authority.
- Runtime cache cannot promote an unavailable capability.
- Protected route activation requires a current snapshot, policy, consent, lease, and bound-content receipt.
- Leases are purpose/scope-bound, single-use, and freshness-limited.
- Unknown side effects block verification.
- Native Goal mutation remains Host-owned.
- Evaluation executable configuration is server-owned; model input cannot choose it.
- Raw model traces and local paths stay out of public artifacts.

## Risk

R0 local planning may run in the bundled control plane. R1 requires stronger runtime validation; R2/R3 remain subject to Codex sandbox, approval, and permission boundaries. A lower-risk routing label never downgrades the Host's own risk decision.

## Dependency decisions

The Plugin lockfile excludes known High and Critical dependency findings before a
release candidate is accepted. A current upstream-tracked Moderate exception in
the MCP SDK's transitive HTTP adapter is documented with its exposure boundary
and removal criterion in the [Plugin dependency security decision](https://github.com/eric861129/Workflow-skill-router/blob/main/docs/governance/plugin-dependency-risk.md).
The Plugin itself starts an MCP stdio transport, not an HTTP listener.

## Report a vulnerability

Follow [SECURITY.md](https://github.com/eric861129/Workflow-skill-router/blob/main/SECURITY.md). Do not include secrets, private repository data, or exploit details in a public issue.

<!-- M4-B adaptive-memory-reference:start -->
## Adaptive Workflow Memory public contract

The public surface contains **20** MCP tools. Memory uses a separate **Operational DB** and **Optional Memory DB**. Managed writes are limited to `managed-personal` and `managed-workspace-local`; User-owned Profile writes still require their original authority.

The four decisions remain separate: policy autonomy, trusted Workspace binding, Profile ownership/target authority, and Runtime/Side-effect execution authority. A trusted root is not a Host write grant.

**Skill consistency** is **unavailable** without **receipt evidence**. A planned route may be `intended-unverified`; it is not activation proof. The Memory Flight Recorder uses `fixture-trace` or sanitized runtime records. Its `deterministic-local-pilot` is **not Model Evidence** and never contains actual Personal Memory.

### Authority decisions

1. Personal Policy establishes the autonomy ceiling.
2. Workspace Policy may reduce but cannot elevate it.
3. Automatic materialization is managed-only and conflict-suppressed.
4. Host Runtime, Skill activation, Side-effect and User-owned Workspace-file authority are never inferred from Memory.
<!-- M4-B adaptive-memory-reference:end -->
