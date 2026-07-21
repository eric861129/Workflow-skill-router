# V2 beta.5 Pilot evidence template

Status: `protocol-frozen-awaiting-real-pilot`

No real Pilot task has been executed or counted by this template. Complete it
only after the real-task inputs and required authority have been separately
authorized. A deterministic validation or dry-run is not Pilot evidence.

## Release truth

- Published V2 remains beta.3.
- Beta.4 is prepared, unpublished source work.
- Beta.5 is unreleased source work awaiting a genuine Pilot.
- This document does not authorize a release, live model use, Host access, or
  production activity.

## Frozen run manifest

Freeze these values before the first real task. Later task records cannot
change thresholds, scoring rules, or the manifest silently.

| Field | Frozen value |
| --- | --- |
| Source revision | `[required before execution]` |
| Runtime/package digest | `[required before execution]` |
| Protocol digest | `[required before execution]` |
| Restricted binding manifest digest | `[required before execution]` |
| Binding-manifest commitment | `[required before execution]` |
| Task-set commitment | `[required before execution]` |
| Reviewer-attestation commitment | `[required before execution]` |
| Reviewer | `[required before execution]` |
| Timestamp | `[required before execution]` |

Any protocol change requires a new digest and a new run. Keep task objectives,
raw prompts, repository or workspace paths, and expected/actual Skill values
inside reviewed restricted evidence.

## Pre-execution restricted binding manifest

Schema: [`evaluation/v2/pilots/restricted-binding-manifest.schema.json`](../../evaluation/v2/pilots/restricted-binding-manifest.schema.json)

Before task 1, create the restricted binding manifest with exactly one record
for each of the 20 frozen slot IDs. Use a per-run secret HMAC-SHA-256 to commit
to the task identity, its source identity, and each complete binding record.
Never publish the secret, task input, source path, raw prompt, or restricted
manifest.

Each record freezes:

- the immutable slot ID;
- non-reversible task and source identity commitments;
- Profile identity commitment and revision digest when Profile-backed;
- `manual_envelope`, `no_explicit_skill`, `explicit_lock`, and
  `router_local_resume` population flags;
- a record-integrity commitment.

The restricted reviewer verifies the secret inputs, distinct task identities,
source bindings, Profile revisions, metric flags, and real-task status. Record
the reviewer attestation before task 1. Public-safe evidence contains only the
binding-manifest commitment, task-set commitment, and reviewer-attestation
commitment. This supports later audit but does not replace human review of
whether each private input is a real task.

All 20 task commitments must be distinct; every source commitment must be
present; the ordered task/source pairs and exact slot set must match the frozen
manifest. The restricted manifest digest must match the frozen run metadata.
Any missing, ambiguous, duplicate, digest-mismatched, or post-start-changed
binding or record makes the entire run invalid, never ineligible.

## Local-work-loop evidence

Protocol: [`evaluation/v2/pilots/local-work-loop-plan.json`](../../evaluation/v2/pilots/local-work-loop-plan.json)

- Required mix: at least 6 Single, 8 Phased, and 6 Goal-like real local tasks.
- Profile coverage: at least 8 real tasks backed by a Personal or Workspace
  Profile.
- Manual envelope correction rate gate: `<= 10%`.
- Unnecessary consent rate for no-explicit-Skill work: `<= 5%`.
- Explicit Skill Lock gate: zero unconsented support Skills.
- Router-owned local resume success gate: `>= 95%`.

Freeze metric membership before task 1. All 20 slots belong to
`manual_envelope`; at least 10 belong to `no_explicit_skill`, at least 4 to
`explicit_lock`, and at least 10 to `router_local_resume`. Populations may
overlap. Every eligible slot requires a final record, and every resume-eligible
slot must be attempted.

The exact measurements are corrected envelopes divided by all 20 slots;
unnecessary prompts divided by frozen no-explicit-Skill slots; unauthorized
support events across at least four Explicit Lock slots; and successful resumes
divided by attempted resume-eligible slots. Missing records or a zero or
under-minimum denominator makes the gate unmet and the run invalid. `0/0` can
never pass.

Sanitized aggregate fields and case-safe diagnostics belong here only after
review. Do not insert objectives, prompts, instruction bodies, paths, secrets,
raw transcripts, expected/actual Skill values, or unreviewed evidence.

## Host evidence lane

Protocol: [`evaluation/v2/pilots/host-conformance-plan.json`](../../evaluation/v2/pilots/host-conformance-plan.json)

Choose exactly one evidence lane and preserve its claim boundary:

1. Offline reference adapter conformance is development evidence only. It does
   not count as a verified Host Pilot.
2. A genuine verified Host Pilot requires actual Host-side authority and
   receipts plus independent human review.
3. When real Host APIs are absent, record a reviewed
   `capability-unavailable` attestation instead of inventing a Pilot result.

None of these preparation steps establishes `hybrid-full`.

## Semantic recommender decision

Decision: `deterministic-default-no-semantic-recommender`.

An experimental proposal is eligible only after real Pilot data shows all of
the following:

- `>=10%` of eligible corrections are attributable to lexical synonym misses;
- `profile preview --explain` rules out deterministic configuration causes;
- a server-configured advisory-only adapter exists and cannot persist a route
  directly.

No Pilot data means the gate is unmet, not a negative performance claim.

## Required authorizations still outstanding

- real local Pilot inputs and permission to execute/count them;
- real Host availability and authority, or permission to attest
  `capability-unavailable`;
- separate live-model quota authorization for Task 13;
- separate external release authorization.
