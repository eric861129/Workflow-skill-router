---
title: Real model evaluation boundary
---

# Evaluation evidence

## Frozen beta.5 Pilot boundary

The local-work-loop and Host conformance protocols are frozen as
`protocol-frozen-awaiting-real-pilot`. No real Pilot task has been executed or
counted. Published beta.3 remains public, beta.4 is prepared, unpublished source
work, and beta.5 is unreleased source work.

The local protocol requires at least twenty real tasks: 6 Single, 8 Phased, and
6 Goal-like, including at least 8 Profile-backed tasks. Before the first task,
the maintainer must freeze the source revision, runtime/package digest,
protocol digest, reviewer, and timestamp. Later records cannot silently change
the scoring gates.

Public Pilot artifacts may contain sanitized aggregates and case-safe
diagnostics only. Objectives, raw prompts, repository/workspace paths,
instruction bodies, secrets, raw transcripts, expected/actual Skill values,
and unreviewed evidence remain restricted.

Before task 1, an independent reviewer must approve a restricted binding
manifest containing exactly 20 records in order: `single-01..06`,
`phased-01..08`, then `goal-01..06`. A per-run secret HMAC-SHA-256 using
`wsr-beta5-pilot-hmac-v1` commits to each opaque task identity, opaque source
identity, Profile identity/revision when used, metric-population flags, and
record integrity. The restricted IDs are reviewer-assigned identifiers, not
objectives, prompts, or paths. Public evidence carries only the
binding-manifest commitment, task-set commitment, and reviewer-attestation
commitment; it cannot reverse task content and does not replace human review
that each input is a real task.

The HMAC input is byte-exact: UTF-8
`workflow-skill-router/beta5-pilot/v1`, NUL, the domain label, NUL, then every
field as `ASCII(decimal byte_length) + 0x3A + UTF-8 field bytes`. There is no
implicit JSON serialization, Unicode normalization, or locale-dependent
conversion. Before task 1, run:

```powershell
python evaluation/v2/pilots/verify_restricted_manifest.py `
  --manifest <restricted-manifest.json> `
  --secret-file <restricted-32-byte-secret.bin>
```

The verifier prints only `valid` and a safe diagnostic `code`.

All task commitments must be distinct, every source commitment must be
present, exact slot IDs and the restricted manifest digest must match frozen
metadata, and no record may change after task 1 starts. Any missing, ambiguous,
duplicate, changed, or digest-mismatched binding makes the run invalid, never
ineligible.

Metric flags are frozen before execution. All 20 slots are manual-envelope;
the 10 no-explicit-Skill slots are `single-01..06` and `goal-01..04`; the four
Explicit Lock slots are `phased-01..04`; and the 10 resume-eligible slots are
`phased-01..08` and `goal-05..06`. No-explicit-Skill and Explicit Lock are
mutually exclusive, and exactly the eight Phased slots are Profile-backed.
Every eligible slot needs a final record and every resume-eligible slot must be
attempted. An under-minimum or zero denominator is invalid and cannot pass as
`0/0`.

Offline reference adapter conformance is development evidence only. A genuine
verified Host Pilot requires actual Host-side authority and receipts plus human
review. If real Host APIs are unavailable, publish a reviewed
`capability-unavailable` attestation; never count the reference adapter as a
Host Pilot or claim `hybrid-full`.

The semantic decision is
`deterministic-default-no-semantic-recommender`. Consider an experimental
proposal only when real Pilot data attributes `>=10%` of corrections to lexical
synonym misses, `profile preview --explain` rules out deterministic
configuration causes, and a server-configured advisory-only adapter exists.
No Pilot data means the gate is unmet, not a negative performance claim.

**Tier 0 Contract** checks deterministic compatibility. Behavior and Outcome require fresh isolated attempts, sealed scoring, paired manifests, and zero hard violations. Without an adapter the run is `manual-required`; without a trusted human attestation the export is `review-required` and contains no score.

Neither `skill-only-fallback` nor `hybrid-full` may self-assert review authority.

Raw results and checkpoints are written only under a verified `restricted/` directory. On Windows the DACL stops inheritance and allows only the current user and SYSTEM; on POSIX the directory and files must verify as `0700` and `0600`. Unprotected transcripts cannot be resumed.

Every run requires a missing or empty output root. Preflight rejects any existing report or artifact before the first attempt, preventing a failed fresh run from leaving a stale sanitized report that could be mistaken for current evidence.

The public report exposes safe case-level diagnostics: counts, match rates, and paired deltas only. Prompts, expected or actual Skill values, rationales, and route payloads remain restricted.

Contract `workflow-skill-router.behavior-routing@2.3.0` keeps the full suite at 13 cases and the beta smoke at six cases. Existing Single, Phased, and Managed Goal structural cases now omit `requested_work_mode`; `profile-explain-miss` replaces `evaluation-manual-required`. The smoke still has one two-turn scoped-consent case, preserving 36 attempts and 42 model turns. Historical 2.2.0 reports retain their original case and instruction digests and are never rescored.

The contract scores public-safe classification source/reason codes, local authority, Profile explain, and unnecessary consent. Goal-bound local mutation, local output that claims activation, direct semantic-candidate persistence, and missing or invalid required evidence are hard violations. Every turn must include the evidence object using the shared public non-oracle vocabulary; it never includes raw prompts, instruction bodies, Profile contents, paths, or scoring expectations. Attempt identity binds the nonce, tool inventory, instruction digest, public case payload digest, model/reference-driver version, and an irreversible scorer-side digest of the private oracle and scoring policy. Resume rejects a transcript produced under a different scoring digest.

The deterministic reference-driver validates the protocol and scoring pipeline; it does not prove real-model behavior. Beta.4 has no new model evidence until an explicitly authorized 36-attempt / 42-turn run is reviewed and attested.

The paired arms now declare different product execution modes instead of pretending both are instruction-only: baseline is `model-only`, candidate is `hybrid-router`. On a candidate consent follow-up, the fresh model returns only `approved`, `rejected`, or `unclear`; the deterministic Router applies that intent to the persisted proposal. Model behavior evidence and deterministic MCP integration evidence must share the same source revision before attestation.
