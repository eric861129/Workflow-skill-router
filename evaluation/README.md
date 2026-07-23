# Workflow Skill Router V2 evaluation

V2 separates deterministic regression fixtures from fresh-model evidence. A passing Contract suite proves that code follows a known routing contract; it does not prove that a model will make the same decision in a fresh task.

## Evidence map

| Location | Evidence | Purpose |
| --- | --- | --- |
| `packages/router-core/tests/fixtures/legacy-v1/` | `T0 contract-only` | Preserve the reviewed 80-case V1 regression value after the legacy public evaluator is retired. |
| `evaluation/v2/cases/` | Runnable public-safe cases | Define paired baseline/candidate inputs for V2. |
| `evaluation/v2/reference_driver.py` | `reference-driver` | Demonstrate protocol, isolation, repeat, and artifact reproducibility without calling a model. |
| `evaluation/v2/adapters/codex_cli_driver.py` | Fresh model transport | Run isolated Codex CLI attempts with user configuration disabled and a strict output schema. |
| `dist/evaluation/` | Local evaluation output | Keep provider traces and attempt directories out of Git; raw/checkpoint files live only under a verified `restricted/` child while the output root contains the sanitized report. |

Evaluation contract `2.3.0` binds every public case, sanitized report, and beta profile to one explicit oracle revision. It covers deterministic envelope classification, Profile explain evidence, current-Phase scoped consent, managed Goal boundaries, and capability-unavailable behavior. The six-case `beta-smoke` suite keeps the frozen 36-attempt / 42-turn budget, while the thirteen-case `full` suite adds a stateful Phase transition and the broader V2 control surface. Multi-turn cases are scored turn by turn; a correct final route cannot hide an incorrect earlier route. Historical reports remain diagnostic and are never rescored against this oracle.

## Deterministic reference run

This run does not use model quota and can never be relabeled as Behavior evidence:

```powershell
$Python = (Get-Command python).Source
python scripts/run-v2-benchmark.py `
  --suite full `
  --evidence-class reference-driver `
  --adapter-executable $Python `
  --adapter-arg evaluation/v2/reference_driver.py `
  --repeats 3 `
  --output-dir dist/evaluation/v2/reference
```

## Paired Codex Behavior smoke

Resolve a native Codex executable that supports the selected model, then review the case/repeat/cost envelope before running. On Windows, pass `codex.exe`, not the npm `codex.ps1` or `codex.cmd` wrapper, so the driver can preserve `shell=False`.

```powershell
$Codex = (Resolve-Path "C:\path\to\native\codex.exe").Path
$Python = (Get-Command python).Source
$Driver = (Resolve-Path "evaluation/v2/adapters/codex_cli_driver.py").Path
$SourceRevision = (git rev-parse HEAD).Trim()
$WorkingTreeStatus = git status --porcelain=v1
if ($WorkingTreeStatus) { throw "Behavior evidence requires a clean checkout." }
$AdapterRevision = (& $Python scripts/run-v2-benchmark.py --print-canonical-adapter-revision).Trim()
$Schema = (Resolve-Path "evaluation/v2/schemas/codex-route-output.schema.json").Path
$AuthSource = Join-Path ([Environment]::GetFolderPath('UserProfile')) ".codex\auth.json"
$RunId = "beta1-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$AttemptRoot = Join-Path (Get-Location) "dist/evaluation/v2/codex-attempts-$RunId"
$OutputRoot = Join-Path (Get-Location) "dist/evaluation/v2/codex-live-$RunId"
& $Codex --version
python scripts/run-v2-benchmark.py `
  --suite beta-smoke `
  --evidence-class behavior `
  --adapter-executable $Python `
  --adapter-arg $Driver `
  --adapter-arg=--codex-executable `
  --adapter-arg $Codex `
  --adapter-arg=--output-schema `
  --adapter-arg $Schema `
  --adapter-arg=--attempt-root `
  --adapter-arg $AttemptRoot `
  --adapter-arg=--timeout-seconds `
  --adapter-arg 150 `
  --adapter-arg=--auth-source `
  --adapter-arg $AuthSource `
  --adapter-arg=--model `
  --adapter-arg gpt-5.6-sol `
  --repeats 3 `
  --timeout-seconds 180 `
  --output-dir $OutputRoot `
  --authorized-source-revision $SourceRevision `
  --authorized-adapter-revision $AdapterRevision `
  --confirm-live-run
```

That is 6 cases × 2 arms × 3 fresh attempts = 36 model attempts. One beta case has a second consent turn, so the authorized provider budget is 42 model turns. Every attempt uses an isolated empty working directory. Baseline and candidate share the task prompt, structured Skill descriptors, tool inventory, Codex executable, output schema, timeout, and case order; only the candidate receives the canonical Router instruction package. The Runner accepts only its current Python executable and the canonical absolute `evaluation/v2/adapters/codex_cli_driver.py` entrypoint; external copies, renamed repository copies, module mode, and ambiguous command forms fail closed before provider execution. Behavior launches use the exact `-I -S -B -X pycache_prefix=<restricted-empty>` interpreter policy and an explicit environment allowlist with no `PYTHON*` import hooks. The protected cache prefix must remain empty before and after provider calls. The adapter revision is a deterministic digest of this launch policy, the canonical relative entrypoint, its local Router Core Python module closure, and the driver-owned vocabulary/schema files. The Runner revalidates the clean full Git commit and authorized closure digest before and after resume inspection, before and after every adapter invocation, and around every checkpoint write. Attempt nonces bind those revisions together with the prompt, capability snapshot, tool-inventory, instruction, model, case, and scoring-spec digests, so changed source, adapter closure, or case evidence cannot resume an older transcript.

Use a new `RunId` for every authorized run. The runner accepts only a missing or empty output root, rejects legacy public `checkpoint.json` or `raw-results.json`, verifies the Windows DACL or POSIX modes before accepting evidence, and exposes only `sanitized-report.json` at the output root. Do not reuse a superseded output or attempt root.

The driver also uses a fresh `HOME` and `CODEX_HOME`, disables plugins and bundled Skills, and copies authentication into that isolated home only for the duration of one turn. The copy is removed in `finally`, including timeout and process-start failure paths. This prevents personal Skills and configuration from contaminating either arm.

## Delta Qualification for a monotonic safety repair

The paired six-case `beta-smoke` run remains the default final Behavior
qualification: 36 attempts and 42 model turns. It is required whenever a
change can alter routing intent, instruction content, scoring, public cases,
model configuration, or the general execution protocol.

A **Delta Qualification** is not a general shortcut. It is permitted only for
one precommitted, named **monotonic** safety repair whose manifest binds all of
the following: one reviewed parent sanitized report, the exact former hard
violation, the only affected case and arm, an allowlisted source diff, and a
machine-checked postcondition. It runs without resume and may only be combined
with—not substituted for—the parent full qualification. Any unlisted source
path, parent digest mismatch, changed model, changed suite, or failed
postcondition fails closed before a provider call.

The currently accepted manifest, `activation-claim-v1`, confirms only the
repair that blocks a local activation claim. It binds the reviewed
`89f342…` parent report, requires `activation_status: "unverified"` in both
the output schema and driver, and fixes the scope to the candidate arm of
`phased-current-boundary`. Its provider budget is exactly **3 attempts / 3
turns**; it does not produce a paired comparison or a new independent full
qualification.

After freezing a clean candidate commit, run the fixed manifest as follows.
Use new output and attempt roots for every execution, and review only the
resulting sanitized report:

```powershell
$Python = (Get-Command python).Source
$Codex = (Resolve-Path "C:\path\to\trusted\codex.exe").Path
$Driver = (Resolve-Path "evaluation/v2/adapters/codex_cli_driver.py").Path
$ParentReport = (Resolve-Path "dist/evaluation/v2/ga-2.0.0-89f342-network4/sanitized-report.json").Path
$SourceRevision = (git rev-parse HEAD).Trim()
$AdapterRevision = (& $Python scripts/run-v2-benchmark.py --print-canonical-adapter-revision).Trim()
$RunId = "delta-activation-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$AttemptRoot = Join-Path (Get-Location) "dist/evaluation/v2/codex-attempts-$RunId"
$OutputRoot = Join-Path (Get-Location) "dist/evaluation/v2/codex-live-$RunId"

python scripts/run-v2-benchmark.py `
  --suite beta-smoke `
  --evidence-class behavior `
  --adapter-executable $Python `
  --adapter-arg $Driver `
  --adapter-arg=--codex-executable `
  --adapter-arg $Codex `
  --adapter-arg=--attempt-root `
  --adapter-arg $AttemptRoot `
  --adapter-arg=--model `
  --adapter-arg gpt-5.6-sol `
  --repeats 3 `
  --timeout-seconds 180 `
  --output-dir $OutputRoot `
  --authorized-source-revision $SourceRevision `
  --authorized-adapter-revision $AdapterRevision `
  --delta-qualification activation-claim-v1 `
  --parent-sanitized-report $ParentReport `
  --confirm-live-run
```

The report must retain the parent evidence binding, record the fixed
`activation-claim-v1` scope, show exactly 3 candidate attempts / 3 model
turns, and contain zero candidate hard violations. A trusted maintainer must
then attest that this narrow evidence bridge and its parent full run together
support the frozen release source.

## Claim and review policy

- `reference-driver` demonstrates orchestration only. It is not Behavior or Outcome evidence.
- Behavior requires at least three fresh contexts per case and complete nonce, prompt, tool-inventory, and trace digests.
- The Codex beta measures routing and consent decisions. Real Skill activation and task Outcome remain `not-observable`, so this run cannot establish `hybrid-full` conformance.
- Missing model identity, token, or cost data is reported as `null` with `metric_status: "unavailable"`; zero is never fabricated.
- Generated reports remain `review-required` and omit a public composite score until a trusted human verifies provenance, redaction, and evidence completeness.
- Raw traces and attempt transcripts remain under ignored `dist/evaluation/`. Publish only a reviewed, sanitized artifact under the public attestation policy.

See [V2 adapter protocol](v2/README.md) for process-level fields, freshness rules, timeouts, and manual-import fallback.
