---
title: V2 Routing Case Studies
description: See how envelope selection, Explicit Skill Lock, and runtime readiness change real routing decisions.
---

## Small documentation fix

**Request:** “Document one API error response.”

**Decision:** `single`, with one documentation-oriented primary SKILL. No consent prompt appears because the user did not name a SKILL. The Router declares expected usage, edits, verifies links, then discloses actual usage.

**Why it matters:** The Router does not turn every request into a workflow or ask permission for ordinary automatic routing.

## Multi-stage API contract change

**Request:** “Add an endpoint, update OpenAPI, regenerate the client, and verify the consumer.”

**Decision:** `phased`.

1. Contract and backend semantics.
2. Generated client propagation.
3. Consumer regression verification.

Each phase selects a new minimal SKILL set and passes a verification gate before the next phase. Skills that are useful only later stay inactive until their phase begins.

**Why it matters:** One broad route would load unrelated capabilities early and blur ownership of failures.

## User names one SKILL

**Request:** “Use `api-designer` only to review this contract.”

**Decision:** `single` plus Explicit Skill Lock. `api-designer` remains active. If a security-sensitive detail justifies another SKILL, the Router proposes it as inactive support and asks once. Rejection leaves the original lock unchanged.

**Why it matters:** User choice is authoritative without blocking a transparent, optional recommendation.

## Cross-repository migration Goal

**Request:** “Continue the API, Web, and documentation migration until the release gate is ready.”

**Decision:** `managed-goal`, with Work Items, dependencies, candidates, evidence receipts, and explicit completion criteria. In the bundled local R0 profile, planning and status work, while scheduling returns `capability-unavailable` until verified Host ports exist.

**Why it matters:** The Router degrades honestly instead of pretending local files provide native Goal mutation.

## Model evaluation request

**Request:** “Prove the new routing behavior is better using real model runs.”

**Decision:** A dry-run manifest can be prepared without quota. Behavior/Outcome execution stays blocked until a trusted operator supplies an executable configuration and explicitly authorizes quota. Results remain unpublished until paired review and attestation pass.

**Why it matters:** A fixture proves the contract shape; it does not prove model behavior. Evaluation cost and publication are separate decisions.

## Capability discovered but not authorized

**Request:** “Use the deployment connector you found to publish now.”

**Decision:** Discovery may show that the connector is installed, but activation remains blocked if Host exposure, authorization, policy, freshness, or side-effect approval is missing.

**Why it matters:** Installation is evidence, not authority.
