---
title: Evaluation Evidence
description: 區分 deterministic contract、fresh model behavior 與 reviewed outcome。
---

<a id="problem"></a>
## 問題

Deterministic fixture 可以證明 parser 與 policy compatibility，卻不能證明 fresh model behavior。單一成功 transcript 也無法證明 reliability；未審查分數不應驅動 release。

<a id="contract"></a>
## 契約

- **T0 Contract**：只包含 deterministic fixtures 與 reference-driver compatibility。
- **Behavior**：每個 case 至少三個 fresh isolated attempts、bounded output、sealed scoring 與 paired baseline/candidate manifests。
- **Outcome**：經審查的 task impact 與 downstream evidence。

Beta smoke 是 6 cases × 3 attempts × 2 arms，共 36 attempts。GA gate 是 12 cases × 3 attempts × 2 arms，共 72 attempts。兩者都需要明確 quota authorization。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "adapter": "trusted-subprocess",
  "attempts_per_case": 3,
  "arms": ["baseline", "candidate"],
  "status": "review-required",
  "public_score": null
}
```

修正版 beta Behavior run 目前仍待授權，因此 public demo 維持 `manual-required`。Reference-driver output 絕不標示為 real-model proof。

<a id="failure-modes"></a>
## Failure modes

- 缺少 configured adapter 時產生 `manual-required`。
- Nonce、case、prompt、tool 或 driver digest mismatch 會 fail closed。
- Hard violation 不受平均 pass rate 影響，直接阻擋 release。
- 缺少 trusted attestation 時維持 `review-required` 並隱藏 public score。

<a id="security-boundary"></a>
## Security 與 authority boundary

Model 不能選 executable、擴張 adapter authorization、讀取 sealed scoring material，或核准自己的報告。Fresh run 使用 isolated home/workspace 與 server-owned adapter registry。Raw traces 不進入 public site data。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.evaluation.test_subprocess_adapter -v
Set-Location ../..
python -m unittest tests.test_v2_benchmark tests.test_codex_cli_driver -v
```
