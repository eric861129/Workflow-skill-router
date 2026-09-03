# ADR 0005: Opt-in adaptive workflow memory

- Status: Proposed
- Date: 2026-09-03

## Context

Workflow Skill Router can load deterministic Personal and Workspace Routing Profiles, classify work envelopes, route each Phase, and preserve Explicit Skill Lock. It does not currently learn repeated user workflows, generate Profile update proposals from execution history, or version Router-mediated Profile writes.

Adding memory creates a different trust and retention boundary from ordinary routing:

- routing state is operational and may be append-only;
- optional workflow history must be disableable and purgeable;
- a repository-owned configuration file must not opt the user into data collection;
- automatically generated rules must not override user-authored rules;
- remembering a Skill Tree must not imply installation, activation, runtime authority, or side-effect authority;
- model output must not directly mutate a persisted Profile.

The existing Routing Profile contract is strict and intentionally contains only matchers and Skill Trees. Adding history, confidence, retention, or write policy to that contract would mix separate concerns.

## Decision

### Default-off policy

Adaptive Workflow Memory is disabled unless a valid Personal Memory Policy explicitly opts in.

The supported autonomy order is:

```text
disabled < observe < reviewed < automatic
```

A Workspace Policy may reduce the effective level but may not increase it.

### Separate Memory Policy contract

Memory configuration uses a new strict, non-executable artifact:

```text
workflow-skill-router/memory-policy@1.0.0
```

It is separate from `workflow-skill-router/routing-profile@1.0.0`.

The canonical representation is JSON. Plugin + MCP may accept JSON or a restricted YAML subset and must canonicalize both before validation and digest calculation.

### Separate optional memory store

Route observations, feedback, patterns, and candidates use an optional local memory store outside the Plugin cache. The store is created only when memory is enabled and supports retention and explicit purge.

The operational append-only event stream is not the sole storage location for optional history.

### Reviewed and automatic writes

`reviewed` mode may produce a Profile Update Proposal, semantic Diff, Backtest, and explicit approval transition.

`automatic` mode may write only Router-managed Personal or Workspace-local Profiles. It may not automatically modify user-owned Personal Profiles or `.codex/workflow-skill-router.json`.

Every Router-mediated Profile write requires:

- strict schema validation;
- profile lint;
- conflict detection;
- expected current digest;
- compare-and-swap;
- atomic replacement;
- a Profile Revision;
- post-write digest validation.

Rollback creates a new forward revision.

### Profile precedence

User-authored Profiles outrank Router-managed Profiles at the same scope.

The effective order is:

```text
explicit Skill Lock
-> user-owned Workspace Profile
-> managed Workspace-local Profile
-> user-owned Personal Profile
-> managed Personal Profile
-> built-in routing
```

### Deterministic-first learning

The first implementation uses deterministic route signatures, pattern mining, confidence categories, and historical backtests.

A semantic recommender remains advisory-only and is considered only after Pilot evidence demonstrates a material deterministic miss rate. Model output cannot directly persist a route.

### Authority remains separate

Memory never:

- installs a Skill or Plugin;
- activates Skill instructions;
- grants filesystem, network, subprocess, or secret access;
- authorizes deployment, publication, or production effects;
- mutates Native Codex Goal.

A remembered route remains `intended-unverified` until Runtime Capability Discovery validates it.

## Consequences

### Positive

- Existing users receive no new data retention by default.
- Users can choose observation-only, reviewed, or automatic managed memory.
- Workspace repositories cannot silently increase memory autonomy.
- Automatic mode is useful without granting it ownership of user-authored files.
- Profile changes are inspectable, reproducible, and reversible.
- Optional history can be deleted independently from operational state.
- Routing Profile remains small and stable.

### Costs

- The runtime gains a second persistence boundary and migration surface.
- Managed Profile precedence must be represented explicitly instead of relying only on Profile priority.
- JSON/YAML sources require canonicalization parity tests.
- Profile revision storage and CAS add implementation complexity.
- Automatic mode may suppress a useful candidate when it conflicts with a manual Profile; this is intentional.

## Rejected alternatives

### Enable memory by default

Rejected because persistence requires an explicit user decision.

### Let Workspace Policy enable memory

Rejected because repository content is not equivalent to personal consent.

### Store all optional history in append-only workflow events

Rejected because optional memory needs bounded retention and deletion.

### Add memory fields to Routing Profile

Rejected because routing preference and memory governance have different schemas, owners, and lifecycles.

### Automatically rewrite user-owned Profiles

Rejected because it weakens user ownership and creates difficult-to-audit drift.

### Use an LLM to learn and persist rules immediately

Rejected because model output is not a deterministic authority for persisted routing policy.

### Treat remembered Skills as activated

Rejected because routing preference, installation, activation, runtime authority, and side effects remain separate decisions.
