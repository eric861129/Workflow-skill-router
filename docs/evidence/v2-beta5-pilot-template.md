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
| Reviewer | `[required before execution]` |
| Timestamp | `[required before execution]` |

Any protocol change requires a new digest and a new run. Keep task objectives,
raw prompts, repository or workspace paths, and expected/actual Skill values
inside reviewed restricted evidence.

## Local-work-loop evidence

Protocol: [`evaluation/v2/pilots/local-work-loop-plan.json`](../../evaluation/v2/pilots/local-work-loop-plan.json)

- Required mix: at least 6 Single, 8 Phased, and 6 Goal-like real local tasks.
- Profile coverage: at least 8 real tasks backed by a Personal or Workspace
  Profile.
- Manual envelope correction rate gate: `<= 10%`.
- Unnecessary consent rate for no-explicit-Skill work: `<= 5%`.
- Explicit Skill Lock gate: zero unconsented support Skills.
- Router-owned local resume success gate: `>= 95%`.

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
