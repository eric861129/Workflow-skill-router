# ADR 0001: V2-first public surface

## Status

Accepted on 2026-07-17.

## Context

Workflow Skill Router began as an instruction-only starter with V1 samples, generated downloads, evaluators, and documentation living beside the emerging V2 runtime. That mixed surface obscured what a new user should install and made historical demonstrations look like current product evidence.

V2 is a hybrid system: the Plugin/MCP runtime supplies deterministic planning, durable local state, truthful capability readiness, and inspectable traces; a separate SKILL-only package remains useful where Plugin loading is unavailable. Neither mode grants permissions or replaces the host's approval policy.

## Decision

- The repository, README, documentation site, examples, and primary navigation are V2-first.
- Plugin/MCP is the primary product path. SKILL-only remains a supported, explicitly limited fallback rather than an emulation of the runtime.
- User-specified SKILLs remain locked. Router-recommended support requires consent only when a concrete extra capability falls outside that lock; automatic routing does not ask a generic consent question.
- V1 is absent from the primary product surface but remains recoverable from the immutable `v1.3.1` tag and release.
- The stable `latest` channel remains pinned to V1 during the beta. `latest-v2` may identify the beta, but promotion of `latest`, publication, and deployment require separate approval.

## Consequences

- New users see one coherent V2 story and can choose Plugin/MCP or SKILL-only without reading internal plans.
- V1 samples, duplicate docs, generated downloads, and old evaluator/gallery surfaces can be removed from the main tree without erasing release history.
- Claims must identify the active mode. SKILL-only cannot claim durable resume, full drift detection, sealed activation, or `hybrid-full`.
- Migration and rollback remain possible through immutable source history rather than duplicated compatibility files on the main branch.
