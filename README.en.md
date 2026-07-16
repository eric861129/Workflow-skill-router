# Workflow Skill Router V2 — English

Workflow Skill Router gives Codex a runtime-aware decision layer for **Single**, **Phased**, and **Managed Goal** work. It discovers actual capability availability, preserves Explicit Skill Lock, asks before adding support, and records evidence-backed state transitions.

## Quickstarts

- **Skill only:** install [`starter/v2/workflow-skill-router`](starter/v2/workflow-skill-router). It reports `skill-only-fallback`; durable resume, CAS, full drift detection, and activation instrumentation remain unobservable.
- **Plugin/MCP:** install the V2 Plugin archive from [`downloads/`](downloads/). It exposes exactly ten typed tools and can reach `hybrid-full` only after verified host handshake and bound-content preflight.

R2/R3 host approval is never lowered. A user-selected SKILL stays primary across small, phased, and Goal work; support requires scoped consent.

## Evaluation

The 80 historical scenarios are **Tier 0 Contract**, not real model evaluation. Behavior/Outcome uses three or more fresh attempts and sealed scoring. No adapter returns `manual-required`; no trusted human attestation returns `review-required` without a score.

## Channels and docs

`latest` and `latest-v1` remain V1.3.1; `latest-v2` carries the V2 alpha. Read [architecture](docs/v2-architecture.md), [upgrade and rollback](docs/v1-to-v2-upgrade.md), and [validation](README.md#validation).
