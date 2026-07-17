---
title: Real model evaluation boundary
---

# Evaluation evidence

**Tier 0 Contract** checks deterministic compatibility. Behavior and Outcome require fresh isolated attempts, sealed scoring, paired manifests, and zero hard violations. Without an adapter the run is `manual-required`; without a trusted human attestation the export is `review-required` and contains no score.

Neither `skill-only-fallback` nor `hybrid-full` may self-assert review authority.

Raw results and checkpoints are written only under a verified `restricted/` directory. On Windows the DACL stops inheritance and allows only the current user and SYSTEM; on POSIX the directory and files must verify as `0700` and `0600`. Unprotected transcripts cannot be resumed.

Every run requires a missing or empty output root. Preflight rejects any existing report or artifact before the first attempt, preventing a failed fresh run from leaving a stale sanitized report that could be mistaken for current evidence.

The public report exposes safe case-level diagnostics: counts, match rates, and paired deltas only. Prompts, expected or actual Skill values, rationales, and route payloads remain restricted.

Contract `workflow-skill-router.behavior-routing@2.1.0` binds the current-Phase oracle separately from the stateful Phase-transition oracle. Multi-turn consent and transition cases are scored at every declared turn, so a correct final route cannot conceal an earlier contract failure. Historical reports retain their original case and instruction digests and are never rescored against a newer oracle. Before execution, the runner recomputes the canonical path-and-SHA-256 manifest and fails closed if the instruction package no longer matches its declared digest.
