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

Evaluation contract `2.2.0` binds every public case, sanitized report, and beta profile to one explicit oracle revision. It corrects the scoped-consent case so the proposed QA support is required by the current Phase's exit evidence instead of a future verification Phase. The six-case `beta-smoke` suite covers auto routing, explicit Skill lock, scoped consent, the current Phase boundary, managed Goal planning, and capability-unavailable behavior. The thirteen-case `full` suite adds a stateful Phase transition and the broader V2 control surface. Multi-turn cases are scored turn by turn; a correct final route cannot hide an incorrect earlier route. Reports produced under `2.1.0` remain diagnostic and are never rescored against this oracle.

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
  --confirm-live-run
```

That is 6 cases × 2 arms × 3 fresh attempts = 36 model attempts. One beta case has a second consent turn, so the authorized provider budget is 42 model turns. Every attempt uses an isolated empty working directory. Baseline and candidate share the task prompt, structured Skill descriptors, tool inventory, Codex executable, output schema, timeout, and case order; only the candidate receives the canonical Router instruction package. Before the first attempt, the runner recomputes the canonical path-and-SHA-256 manifest and rejects any mismatch with the declared instruction digest. Attempt nonces bind the prompt, capability snapshot, and tool-inventory digests, so a changed case cannot resume an older transcript.

Use a new `RunId` for every authorized run. The runner accepts only a missing or empty output root, rejects legacy public `checkpoint.json` or `raw-results.json`, verifies the Windows DACL or POSIX modes before accepting evidence, and exposes only `sanitized-report.json` at the output root. Do not reuse a superseded output or attempt root.

The driver also uses a fresh `HOME` and `CODEX_HOME`, disables plugins and bundled Skills, and copies authentication into that isolated home only for the duration of one turn. The copy is removed in `finally`, including timeout and process-start failure paths. This prevents personal Skills and configuration from contaminating either arm.

## Claim and review policy

- `reference-driver` demonstrates orchestration only. It is not Behavior or Outcome evidence.
- Behavior requires at least three fresh contexts per case and complete nonce, prompt, tool-inventory, and trace digests.
- The Codex beta measures routing and consent decisions. Real Skill activation and task Outcome remain `not-observable`, so this run cannot establish `hybrid-full` conformance.
- Missing model identity, token, or cost data is reported as `null` with `metric_status: "unavailable"`; zero is never fabricated.
- Generated reports remain `review-required` and omit a public composite score until a trusted human verifies provenance, redaction, and evidence completeness.
- Raw traces and attempt transcripts remain under ignored `dist/evaluation/`. Publish only a reviewed, sanitized artifact under the public attestation policy.

See [V2 adapter protocol](v2/README.md) for process-level fields, freshness rules, timeouts, and manual-import fallback.
