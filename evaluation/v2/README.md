# V2 model evaluation adapters

## Frozen formal GA-candidate Pilot protocols

The safe preparation artifacts are now frozen with
`execution_status: protocol-frozen-awaiting-real-pilot`:

- [`pilots/local-work-loop-plan.json`](pilots/local-work-loop-plan.json) freezes
  the twenty-slot real local task mix, manifest, scoring gates, and sanitized
  public evidence boundary.
- [`pilots/restricted-binding-manifest.schema.json`](pilots/restricted-binding-manifest.schema.json)
  defines the private pre-execution bindings. Exactly 20 records use a per-run
  secret HMAC-SHA-256 for task/source identity, Profile revision, population
  flags, and record integrity; the actual manifest and secret never become
  public.
- [`pilots/verify_restricted_manifest.py`](pilots/verify_restricted_manifest.py)
  independently recomputes the byte-exact `wsr-beta5-pilot-hmac-v1`
  commitments and returns only a safe `valid`/`code` result before task 1.
- [`pilots/host-conformance-plan.json`](pilots/host-conformance-plan.json) keeps
  offline reference conformance, a genuine verified Host Pilot, and reviewed
  `capability-unavailable` evidence in separate lanes.
- [`docs/evidence/v2-beta5-pilot-template.md`](../../docs/evidence/v2-beta5-pilot-template.md)
  is the maintainer evidence template.

No real Pilot task has been executed or counted. Published beta.3 remains the
historical V2 snapshot, while `v2.0.0` is the prepared GA candidate and is not
yet released.
These protocols do not authorize a live model, a real Host, or a release.

The binding-manifest commitment, task-set commitment, and reviewer-attestation
commitment must be frozen before task 1. The restricted reviewer verifies real
task status and uniqueness; commitments support audit but do not replace human
review. Metric populations are also frozen: 20 manual-envelope slots, at least
10 no-explicit-Skill slots, at least 4 Explicit Lock slots, and at least 10
resume-eligible slots. Missing or changed records, duplicate commitments,
digest mismatch, or an under-minimum denominator makes the run invalid, never
ineligible; `0/0` never passes.

The exact ordered slots are `single-01..06`, `phased-01..08`, and
`goal-01..06`. Only the eight Phased slots are Profile-backed. Population
membership is fixed at 20 manual-envelope, 10 no-explicit-Skill, 4 Explicit
Lock, and 10 resume-eligible slots; no-explicit-Skill and Explicit Lock are
mutually exclusive. Restricted raw task/source identities are opaque reviewer
IDs, never objectives, prompts, or paths. A source identity is a unique
task-specific source snapshot or brief, not a shared repository identity.

`attested_at` and `frozen_at` use canonical RFC3339 UTC
`YYYY-MM-DDTHH:MM:SSZ`. The reviewer HMAC binds `attested_at`, the manifest HMAC
binds `frozen_at`, and the verifier requires `attested_at <= frozen_at`. A
future real-Pilot runner must require `task_1_started_at > frozen_at` before it
counts task 1; that execution check has not been performed.

The HMAC message is UTF-8 `workflow-skill-router/beta5-pilot/v1`, NUL, the
domain label, NUL, then each field encoded as `ASCII(decimal byte_length) +
0x3A + UTF-8 field bytes`. It performs no implicit JSON serialization, Unicode
normalization, or locale-dependent conversion. Verify the frozen manifest
before task 1:

```powershell
python evaluation/v2/pilots/verify_restricted_manifest.py `
  --manifest <restricted-manifest.json> `
  --secret-file <restricted-32-byte-secret.bin>
```

Commitments are non-reversible without the per-run secret and support later
audit, but they do not replace human review that every input is a real task.

The default remains
`deterministic-default-no-semantic-recommender`. An experimental recommender is
eligible only if real Pilot data attributes `>=10%` of corrections to lexical
synonym misses, `profile preview --explain` rules out deterministic
configuration causes, and a server-configured advisory-only adapter exists.
No Pilot data means the gate is unmet, not a negative performance claim.

Workflow Skill Router V2 evaluates routing behavior through a sealed subprocess boundary. The adapter is an execution transport, not a scorer: it receives only an opaque case ID, the current prompt, the allowed tool names, a nonce, and an opaque provider context. Scoring keys and expected answers never cross this boundary.

## Evidence classes

| Evidence class | What it proves | Release use |
| --- | --- | --- |
| `reference-driver` | The protocol, orchestration, and artifact pipeline are reproducible. | Contract and smoke evidence only. It is permanently labeled and cannot be promoted to Behavior evidence. |
| `fresh-model-execution` | A configured provider created fresh model contexts and returned real turns. | Behavior or Outcome evidence after integrity checks and review. |
| `manual-import` | An external run was imported with provenance. | Review-required fallback when no trusted adapter is configured. |

Contract or reference-driver results do **not** prove real-model routing quality. Public benchmark claims must name the model/provider configuration, run count, case digest, and evidence class.

## Versioned scoring contract

Public cases and profiles are bound to `workflow-skill-router.behavior-routing` revision `2.3.0`. The full suite remains 13 cases: the existing Single, Phased, and Managed Goal structural cases now omit `requested_work_mode` and bind public-safe classification evidence, while `profile-explain-miss` replaces `evaluation-manual-required`. The six-case beta smoke keeps one two-turn consent case, so a future authorized run remains 36 attempts and 42 model turns. The prepared GA candidate carries the sealed Contract 2.3.0 classification coverage without changing the frozen execution budget; historical 2.2.0 reports retain their original case and instruction digests and are never rescored.

Contract 2.3.0 adds aggregate dimensions for envelope source, classification reasons, local authority, Profile explain, and unnecessary consent. It also treats goal-bound local mutation, a local activation claim, direct semantic-candidate persistence, and missing or invalid required evidence as hard violations. Every turn must return `evaluation_evidence` using the public, non-oracle [reason-code vocabulary](reason-code-vocabulary.json). Expected evidence remains in the private scoring oracle; it is excluded from the public case payload and execution driver.

The server-side scoring-spec digest seals every private route/evidence oracle plus the scoring policy, public vocabulary, and deterministic runner source bytes. The digest is embedded only as an irreversible segment of the attempt identity and sanitized server-side metadata. Resume fails closed when an otherwise identical execution transcript was produced under a different scoring spec.

The reference-driver validates deterministic protocol and scoring composition only; it does not prove real-model behavior. No fresh final GA model qualification exists until a frozen 36-attempt / 42-turn run receives explicit quota authorization and its sanitized output is reviewed and attested.

Historical reports keep their original case and instruction digests. Never rescore an older run against a newer contract revision. The runner recomputes the canonical path-and-SHA-256 manifest before execution and fails closed when the instruction package no longer matches its declared digest.

## Process protocol

Each `start_attempt` or `execute_turn` is one process invocation:

1. The host writes one UTF-8 JSON object to stdin.
2. The driver writes one UTF-8 JSON object to stdout and exits with code `0`.
3. `start_attempt` returns a fresh, opaque `context_id` bound to the supplied `attempt_nonce`.
4. Later turns return the same nonce and context. A mismatch, reused context, malformed JSON, non-zero exit, timeout, or oversized output invalidates the attempt.

The normative shape is [adapter-protocol.schema.json](adapter-protocol.schema.json). The default timeout is 120 seconds per invocation and the default combined stdout/stderr limit is 1 MiB. Hosts may lower either limit. Provider sessions, credentials, and retry policy remain driver-owned.

## Trusted configuration boundary

The executable is configured by the CLI or MCP host as an absolute path plus separate argv items. The adapter always uses `shell=False`. On Windows, configure a native executable rather than a PowerShell or batch wrapper. Model/MCP requests cannot submit an executable, path, environment, command string, or adapter kind; they carry only an authorization reference and sealed-case reference. Environment variables are inherited from the trusted host process and are never accepted from model arguments.

The Codex driver creates a fresh `HOME`, `CODEX_HOME`, and empty workspace for every attempt. Plugins and bundled Skills are disabled, personal configuration is ignored, and authentication is copied into the isolated home only around one process invocation before being deleted in `finally`. This is required for a defensible no-router baseline.

The comparison arms receive the same structured Skill catalog. Each descriptor contains a canonical ID, description, domains, stages, and baseline availability. A public case may add a verified capability snapshot that changes activation readiness without changing semantic Skill intent. The Router instruction package is the only permitted difference between baseline and candidate.

## Protected artifacts and safe diagnostics

The runner creates and verifies `restricted/` before writing raw evidence. `restricted/checkpoint.json`, `restricted/raw-results.json`, attempt transcripts, failure diagnostics, and temporary authentication use fail-closed host permissions: POSIX mode checks or a protected Windows DACL limited to the current user and SYSTEM. An unprotected transcript is not eligible for resume.

If an output root contains any existing entry, preflight stops before the first attempt. Legacy public `checkpoint.json` or `raw-results.json` receive a dedicated integrity error. Use a new empty output root; the runner never hides a stale sanitized report or raw evidence behind a new protection claim.

Only `sanitized-report.json` remains in the public output root. Its `case_diagnostics` contains case IDs, counts, match rates, and candidate-minus-baseline deltas. It never includes prompts, expected or actual Skill values, rationales, or route payloads. Raw evidence remains local and restricted.

Preview a reference-driver configuration:

```powershell
$Python = (Get-Command python).Source
workflow-skill-router evaluation run `
  --profile behavior `
  --evidence-class reference-driver `
  --adapter subprocess `
  --adapter-executable $Python `
  --adapter-arg evaluation/v2/reference_driver.py `
  --repeats 3
```

For a real Behavior or Outcome run, use `--evidence-class fresh-model-execution` and explicitly add `--confirm-live-run`. This confirmation matters because providers may incur quota, latency, or monetary cost. The CLI prints a dry-run manifest before execution orchestration consumes it.

## Freshness and failure handling

- Every repeat must create a distinct provider context; a driver must not reuse chat/session IDs.
- The nonce is supplied by the orchestrator and must be echoed unchanged.
- The opaque context is the only driver state returned to later turns.
- A failed or ambiguous attempt is evidence of failure, not a reason to relabel or silently synthesize output.
- When a trusted adapter is unavailable, export a manual bundle and keep the resulting evidence review-required.
