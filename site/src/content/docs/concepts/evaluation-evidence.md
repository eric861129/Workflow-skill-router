---
title: Evaluation Evidence
description: Separate deterministic contracts from fresh model behavior and reviewed outcomes.
---

<a id="problem"></a>
## Problem

A deterministic fixture can prove parser and policy compatibility while saying nothing about fresh model behavior. A single successful transcript also cannot establish reliability, and unreviewed scores should not drive a release.

<a id="contract"></a>
## Contract

- **T0 Contract**: deterministic fixtures and reference-driver compatibility only.
- **Behavior**: at least three fresh isolated attempts per case, bounded output, sealed scoring, and paired baseline/candidate manifests.
- **Outcome**: reviewed task impact and downstream evidence.

The beta smoke uses six cases, three attempts, and two arms: 36 attempts. One beta case includes a second consent turn, so the provider executes 42 model turns. The GA gate uses 13 cases with the same repeat and arm count: 78 attempts and 96 model turns. Both need explicit quota authorization for the complete turn budget.

The baseline arm is `model-only`; the candidate arm is `hybrid-router`. For a scoped-consent follow-up, the model is evaluated on intent classification while the final route is produced by the persisted deterministic transition. SKILL-only consent evidence remains advisory and cannot satisfy the hybrid consent-safety gate.

<a id="example"></a>
## State, input, and output example

```json
{
  "adapter": "trusted-subprocess",
  "attempts_per_case": 3,
  "arms": ["baseline", "candidate"],
  "status": "review-required",
  "public_score": null
}
```

The corrected beta Behavior run is currently pending authorization, so the public demo remains `manual-required`. Reference-driver output is never labeled real-model proof.

<a id="failure-modes"></a>
## Failure modes

- Missing configured adapter produces `manual-required`.
- Nonce, case, prompt, tool, or driver digest mismatch fails closed.
- Hard violations block release regardless of average pass rate.
- Missing trusted attestation keeps export `review-required` and suppresses a public score.

<a id="security-boundary"></a>
## Security and authority boundary

The model cannot choose an executable, widen adapter authorization, access sealed scoring material, or approve its own report. Fresh runs use isolated home/workspace state and a server-owned adapter registry. Raw traces and checkpoints remain under a host-permission-verified `restricted/` directory; only safe aggregate case diagnostics may enter a reviewed public report.

<a id="verify"></a>
## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.evaluation.test_subprocess_adapter tests.evaluation.test_hybrid_consent -v
Set-Location ../..
python -m unittest tests.test_v2_benchmark tests.test_codex_cli_driver -v
```
