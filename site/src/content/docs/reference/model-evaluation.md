---
title: Real model evaluation boundary
---

# Evaluation evidence

**Tier 0 Contract** checks deterministic compatibility. Behavior and Outcome require fresh isolated attempts, sealed scoring, paired manifests, and zero hard violations. Without an adapter the run is `manual-required`; without a trusted human attestation the export is `review-required` and contains no score.

Neither `skill-only-fallback` nor `hybrid-full` may self-assert review authority.

Raw results and checkpoints are written only under a verified `restricted/` directory. On Windows the DACL stops inheritance and allows only the current user and SYSTEM; on POSIX the directory and files must verify as `0700` and `0600`. Unprotected transcripts cannot be resumed.

Every run requires a missing or empty output root. Preflight rejects any existing report or artifact before the first attempt, preventing a failed fresh run from leaving a stale sanitized report that could be mistaken for current evidence.

The public report exposes safe case-level diagnostics: counts, match rates, and paired deltas only. Prompts, expected or actual Skill values, rationales, and route payloads remain restricted.

Contract `workflow-skill-router.behavior-routing@2.3.0` keeps the full suite at 13 cases and the beta smoke at six cases. Existing Single, Phased, and Managed Goal structural cases now omit `requested_work_mode`; `profile-explain-miss` replaces `evaluation-manual-required`. The smoke still has one two-turn scoped-consent case, preserving 36 attempts and 42 model turns. Historical 2.2.0 reports retain their original case and instruction digests and are never rescored.

The contract scores public-safe classification source/reason codes, local authority, Profile explain, and unnecessary consent. Goal-bound local mutation, local output that claims activation, and direct semantic-candidate persistence are hard violations. The optional evidence object is allowlisted and never includes raw prompts, instruction bodies, Profile contents, paths, or scoring expectations. Attempt identity binds the nonce, tool inventory, instruction digest, public case payload digest, and model/reference-driver version.

The deterministic reference-driver validates the protocol and scoring pipeline; it does not prove real-model behavior. Beta.4 has no new model evidence until an explicitly authorized 36-attempt / 42-turn run is reviewed and attested.

The paired arms now declare different product execution modes instead of pretending both are instruction-only: baseline is `model-only`, candidate is `hybrid-router`. On a candidate consent follow-up, the fresh model returns only `approved`, `rejected`, or `unclear`; the deterministic Router applies that intent to the persisted proposal. Model behavior evidence and deterministic MCP integration evidence must share the same source revision before attestation.
