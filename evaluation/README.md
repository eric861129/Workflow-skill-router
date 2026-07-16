# Workflow Skill Router V2 evaluation

V2 separates deterministic regression fixtures from fresh-model evidence. A passing Contract suite proves that code follows a known routing contract; it does not prove that a model will make the same decision in a fresh task.

## Evidence map

| Location | Evidence | Purpose |
| --- | --- | --- |
| `packages/router-core/tests/fixtures/legacy-v1/` | `T0 contract-only` | Preserve the reviewed 80-case V1 regression value after the legacy public evaluator is retired. |
| `evaluation/v2/cases/` | Runnable public-safe cases | Define paired baseline/candidate inputs for V2. |
| `evaluation/v2/reference_driver.py` | `reference-driver` | Demonstrate protocol, isolation, repeat, and artifact reproducibility without calling a model. |
| `evaluation/v2/adapters/codex_cli_driver.py` | Fresh model transport | Run isolated Codex CLI attempts with user configuration disabled and a strict output schema. |
| `dist/evaluation/` | Local raw and generated output | Keep provider traces, attempt directories, and reports out of Git. |

The six-case `beta-smoke` suite covers auto routing, explicit Skill lock, scoped consent, phased work, managed Goal work, and capability-unavailable behavior. The twelve-case `full` suite is the broader V2 gate.

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
& $Codex --version
python scripts/run-v2-benchmark.py `
  --suite beta-smoke `
  --evidence-class behavior `
  --adapter-executable $Python `
  --adapter-arg evaluation/v2/adapters/codex_cli_driver.py `
  --adapter-arg=--codex-executable `
  --adapter-arg $Codex `
  --adapter-arg=--model `
  --adapter-arg gpt-5.6-sol `
  --repeats 3 `
  --output-dir dist/evaluation/v2/codex-live `
  --confirm-live-run
```

That is 6 cases × 2 arms × 3 fresh attempts = 36 model attempts. Every attempt uses an isolated empty working directory. Baseline and candidate share the task prompt, explicit SKILL catalog, tool inventory, Codex executable, output schema, timeout, and case order; only the candidate receives the canonical Router instruction package. Attempt nonces bind the prompt and tool-inventory digests, so a changed case cannot resume an older transcript.

The driver also uses a fresh `HOME` and `CODEX_HOME`, disables plugins and bundled Skills, and copies authentication into that isolated home only for the duration of one turn. The copy is removed in `finally`, including timeout and process-start failure paths. This prevents personal Skills and configuration from contaminating either arm.

## Claim and review policy

- `reference-driver` demonstrates orchestration only. It is not Behavior or Outcome evidence.
- Behavior requires at least three fresh contexts per case and complete nonce, prompt, tool-inventory, and trace digests.
- The Codex beta measures routing and consent decisions. Real Skill activation and task Outcome remain `not-observable`, so this run cannot establish `hybrid-full` conformance.
- Missing model identity, token, or cost data is reported as `null` with `metric_status: "unavailable"`; zero is never fabricated.
- Generated reports remain `review-required` and omit a public composite score until a trusted human verifies provenance, redaction, and evidence completeness.
- Raw traces and attempt transcripts remain under ignored `dist/evaluation/`. Publish only a reviewed, sanitized artifact under the public attestation policy.

See [V2 adapter protocol](v2/README.md) for process-level fields, freshness rules, timeouts, and manual-import fallback.
