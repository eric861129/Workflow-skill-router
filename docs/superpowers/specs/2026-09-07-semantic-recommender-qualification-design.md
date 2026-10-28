# M5 Semantic Recommender Qualification Design

**Status:** Proposed — evidence collection and review only  
**Date:** 2026-09-07  
**Depends on:** Adaptive Workflow Memory M0–M4, ADR 0004, ADR 0005  
**Decision owner:** Repository maintainer  

## 1. Purpose

M5 determines whether Workflow Skill Router has a material routing problem that cannot be solved adequately by its deterministic matcher, Profile configuration, aliases, negative constraints, or capability handling.

This stage does **not** add a Semantic Recommender to production. It defines a privacy-safe real-pilot protocol, an error taxonomy, frozen baselines, metrics, and an explicit Go／No-Go decision gate. A Semantic Recommender implementation may begin only after a separate qualification report is reviewed and accepted.

The central question is:

> After configuration, capability, authority, consent, work-mode, and user-preference errors are excluded, do lexical or compositional meaning misses account for enough real routing corrections to justify a semantic advisory layer?

## 2. Current evidence is insufficient for implementation

M4-B provides deterministic fixtures and a 20-record local Pilot. Those records verify contracts, data flow, privacy boundaries, and reproducibility. They are explicitly labeled:

```text
evidence_class: deterministic-local-pilot
claim: not-model-evidence
```

They do not represent naturally occurring requests, fresh model attempts, or independent user corrections. Therefore they cannot authorize Semantic Recommender implementation.

M5 requires new, opt-in, real-pilot evidence collected after M4-B is merged.

## 3. Hard boundaries

The qualification stage preserves every existing authority boundary:

- Memory remains `default-off`.
- No live-model or embedding call runs in default CI.
- No provider quota is consumed by repository test workflows.
- No raw Prompt, complete Objective, local path, file content, Tool Arguments, Secrets, or Skill Instruction Body is retained for qualification.
- No background collection daemon is introduced.
- No Semantic Candidate is persisted into a Routing Profile.
- No semantic result installs or activates a Skill.
- No semantic result grants Runtime, Filesystem, Network, Subprocess, Secret, Deployment, Publication, or Production authority.
- No semantic result changes a Native Codex Goal.
- Explicit Skill Lock remains authoritative.
- User-owned Profiles remain authoritative over Router-managed Profiles.
- A Workspace cannot elevate the Personal Memory Policy ceiling.
- Semantic output, if later qualified, must begin as `advisory-only` and `intended-unverified`.

## 4. Stage topology

M5 is split into qualification checkpoints rather than one implementation branch.

| Stage | Deliverable | Production semantic routing? |
| --- | --- | ---: |
| M5-Q0 | Qualification design, taxonomy, protocol, report template | No |
| M5-Q1 | Reviewed, opt-in structured correction capture | No |
| M5-Q2 | Real pilot conducted over an agreed time window | No |
| M5-Q3 | Offline deterministic and semantic comparison report | No |
| M5-Q4 | Go／No-Go ADR | No |
| M5-I0 | Separate semantic architecture spec, only after `GO` | Still no, until separately approved |

This document is M5-Q0. Q1–Q4 each require their own Branch, Draft PR, exact-head verification, and maintainer approval.

## 5. Unit of analysis

The primary unit is one **eligible routing decision**. A decision is eligible only when:

1. the Router produced a route from a valid request and current Profile set;
2. relevant Skills and required capabilities were discoverable;
3. the request was not governed by a conflicting Explicit Skill Lock;
4. required authority and consent decisions were known;
5. the user either accepted the route or supplied a structured correction;
6. the record is distinct from retry, Resume, or idempotent replay;
7. qualification collection was explicitly enabled for that pilot;
8. the record contains only bounded structured evidence.

A **corrected decision** is an eligible decision for which the user selected an expected route that differs materially in work mode, primary Skill, support Skill set, phase order, or applicable Profile rule.

## 6. Error taxonomy

Every corrected decision receives exactly one primary reason and zero or more secondary dimensions.

### 6.1 Potentially semantic reasons

| Reason code | Meaning |
| --- | --- |
| `lexical-synonym-miss` | The intended concept used a synonym absent from the current deterministic matcher. |
| `multilingual-equivalence-miss` | Equivalent wording across supported languages failed to match. |
| `compositional-intent-miss` | Individual words existed, but their combination changed the intended route. |
| `negative-constraint-miss` | A negation or exclusion should have prevented a route. |
| `context-relation-miss` | Structured context and objective meaning needed to be combined to select the route. |
| `semantic-ambiguity` | Two routes were genuinely plausible and deterministic evidence could not disambiguate them. |

### 6.2 Non-semantic confounders

| Reason code | Meaning |
| --- | --- |
| `profile-configuration-error` | A missing, disabled, stale, conflicting, or overly broad Profile rule caused the result. |
| `alias-configuration-gap` | A bounded alias entry would deterministically solve the miss without broader semantic inference. |
| `capability-unavailable` | The intended Skill or required capability was not available. |
| `skill-identity-error` | Skill identity, version, or digest was unknown or non-canonical. |
| `work-mode-classification-error` | Single／Phased／Managed Goal classification was wrong independently of rule matching. |
| `authority-or-consent-denied` | Runtime, side-effect, Host, or support-Skill consent prevented the expected route. |
| `explicit-lock-conflict` | The expected route contradicted an explicit user lock. |
| `user-preference-changed` | The user changed the desired workflow after the route was produced. |
| `insufficient-request-evidence` | The request did not contain enough evidence for a reliable route. |
| `record-integrity-failure` | The observation, receipt, Profile snapshot, or comparison binding was incomplete. |
| `other-non-semantic` | A reviewed non-semantic cause not represented above. |

Non-semantic records remain useful for product quality, but they are excluded from the Semantic Recommender numerator.

## 7. Privacy-safe pilot record

A qualification record stores bounded structure only:

```json
{
  "schema_id": "workflow-skill-router/semantic-qualification-record",
  "schema_version": "1.0.0",
  "record_id": "qualification:...",
  "pilot_id": "pilot:...",
  "workflow_run_digest": "sha256:...",
  "recorded_at": "2026-09-07T00:00:00Z",
  "request_language": "zh-TW",
  "work_mode_planned": "phased",
  "work_mode_expected": "phased",
  "planned_route_digest": "sha256:...",
  "expected_route_digest": "sha256:...",
  "matched_profile_source": "user-personal",
  "primary_reason": "lexical-synonym-miss",
  "secondary_dimensions": ["domain:api"],
  "deterministic_fix_candidate": "alias",
  "raw_text_retained": false,
  "review_status": "adjudicated"
}
```

The Pilot UI or CLI may transiently show the current request to the user who is correcting it, but the qualification artifact must never retain that raw text. An optional missing alias may be saved only as an explicitly supplied, bounded normalized token; it is not copied automatically from the request.

## 8. Review and adjudication

Classification is not delegated to a model.

1. The correcting user selects a preliminary reason code.
2. A reviewer checks the structured route, Profile source, capability state, consent state, and correction dimensions.
3. Ambiguous or semantic classifications receive a second independent review.
4. Disagreement is resolved by adjudication and recorded as a reason-code transition, not free-form hidden state.
5. At least 20% of eligible records and every potentially semantic corrected record receive dual review.
6. The report publishes inter-review agreement for primary reason codes.

Records without completed adjudication cannot qualify M5.

## 9. Frozen comparison arms

The analysis compares three frozen arms against the same adjudicated records.

### Arm A — Current deterministic baseline

The exact released lexical／domain／tag／work-mode matcher and Profile revision used when the decision occurred.

### Arm B — Deterministic remediation

A bounded remediation generated from the training portion only:

- aliases;
- exclusions and negative constraints;
- positive／negative examples used as deterministic tests;
- Profile priority or scope correction;
- work-mode rule correction where independently justified.

Arm B must not inspect the held-out evaluation labels while being configured.

### Arm C — Offline semantic advisory prototype

A non-production prototype may rank or abstain on held-out records. It cannot write a Profile or influence a live route. Its input must be privacy-reviewed and ephemeral; retained output is limited to candidate identifiers, ranking, confidence class, abstention, latency class, and evaluation Digests.

A model or embedding provider is never invoked from default CI. Any external evaluation is an explicit, separately authorized operator action with cost and data-handling disclosure.

## 10. Dataset sufficiency

A final Go／No-Go report requires all of the following:

- at least 100 eligible real routing decisions;
- at least 25 adjudicated corrected decisions;
- at least 3 routing domains;
- at least 2 independent Workspaces or projects;
- at least 14 calendar days of collection;
- no single Workspace contributes more than 60% of eligible decisions;
- at least 20% of all records are dual-reviewed;
- every potentially semantic corrected record is dual-reviewed;
- zero unresolved record-integrity failures in the analysis set.

Until every condition is met, the decision is `INSUFFICIENT_EVIDENCE`, not `NO-GO`.

## 11. Metrics

The report must publish counts and confidence intervals where meaningful, not only percentages.

### 11.1 Cause metrics

- eligible decision count;
- corrected decision count and correction rate;
- count and share by primary reason;
- semantic-miss share among adjudicated corrections;
- alias-remediable share;
- configuration／capability／authority confounder share;
- inter-review agreement;
- abstention／insufficient-evidence rate.

### 11.2 Routing metrics

Measured on a held-out evaluation partition:

- top-1 expected-route agreement;
- top-3 expected-route recall when ranking is supported;
- unexpected-match rate;
- false-positive route expansion rate;
- abstention rate;
- regression count on previously correct deterministic routes;
- p50／p95 local latency class;
- external-call count and estimated cost, if an authorized external prototype is used.

### 11.3 Governance metrics

- raw-text retention count, which must remain zero;
- unauthorized Profile writes, which must remain zero;
- authority-boundary violations, which must remain zero;
- Explicit Skill Lock violations, which must remain zero;
- non-advisory semantic actions, which must remain zero.

## 12. Proposed Go／No-Go decision

The report records one of `GO`, `NO-GO`, or `INSUFFICIENT_EVIDENCE`.

### 12.1 GO

A separate Semantic Recommender architecture spec may be proposed only if all conditions hold:

1. dataset sufficiency is met;
2. at least 30% of adjudicated corrections are potentially semantic after all confounders are excluded;
3. deterministic remediation does not recover at least 70% of those semantic misses without increasing unexpected matches beyond 5%;
4. the offline semantic arm improves held-out top-1 agreement by at least 10 percentage points over the stronger of Arm A and Arm B, or recovers at least 60% of the remaining semantic misses;
5. unexpected-match increase is at most 5 percentage points;
6. every governance metric remains zero-violation;
7. latency, cost, provider terms, and data handling are acceptable to the maintainer;
8. the maintainer approves the qualification report and a new ADR.

### 12.2 NO-GO

The result is `NO-GO` when the dataset is sufficient and one or more of the following is true:

- potentially semantic causes account for less than 20% of adjudicated corrections;
- deterministic aliases／Profiles recover at least 70% of semantic misses within the false-positive limit;
- semantic advice does not materially outperform the deterministic remediation arm;
- privacy, authority, latency, cost, reproducibility, or explainability requirements are not met.

The interval between 20% and 30%, or a mixed metric result, requires an explicit maintainer judgment and is not treated as automatic approval.

## 13. Output of a GO decision

A `GO` does not merge semantic routing. It authorizes a new architectural design cycle whose minimum constraints are:

- advisory-only Candidate generation;
- deterministic route remains authoritative by default;
- semantic output is never directly persisted;
- explicit user approval is required before any Profile proposal;
- complete provenance and reason disclosure;
- confidence classes plus abstention;
- fixed timeout, budget, and fail-closed fallback;
- provider-independent adapter boundary;
- local-only option evaluated first;
- no automatic installation, activation, authority grant, or Native Goal mutation;
- kill switch and rollback documented before implementation.

## 14. Output of a NO-GO decision

A `NO-GO` directs work toward deterministic improvements instead:

- alias dictionaries;
- exclusion／negative constraints;
- Profile lint and conflict diagnostics;
- improved work-mode classification;
- capability discovery and missing-Skill explanation;
- clearer correction reason UX;
- additional deterministic tests derived from adjudicated records.

The qualification dataset may be retained only under the approved Memory Policy and retention settings.

## 15. M5-Q0 acceptance criteria

M5-Q0 is complete when:

1. this design is reviewed and merged;
2. the taxonomy distinguishes semantic misses from every identified confounder;
3. qualifying and non-qualifying evidence classes are explicit;
4. minimum dataset and decision thresholds are explicit;
5. raw-text retention remains prohibited;
6. default CI and production routing remain unchanged;
7. no Semantic Recommender code, provider dependency, embedding index, or model call is added;
8. the next approved action is M5-Q1 structured pilot instrumentation—not semantic production implementation.
