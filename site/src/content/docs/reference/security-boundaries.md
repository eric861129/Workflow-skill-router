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
