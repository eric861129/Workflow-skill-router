---
title: Routing Envelopes
description: 選擇 Single、Phased 或 Managed Goal，同時避免 over-routing。
---

<a id="problem"></a>
## 問題

把所有需求當成一步會遺失驗證邊界；把所有需求都當成大型專案則增加規劃成本與 prompt fatigue。Router 必須選擇能保留重要依賴的最小結構。

<a id="contract"></a>
## 契約

- `single`：一個有界意圖、單一階段，沒有 resumable dependency graph。
- `phased`：包含兩個以上不同階段或 domain；每個 Phase 獨立重新路由。
- `managed-goal`：resumable、跨 repo、多 milestone、dependency DAG，或正在進行 Goal progress/steer。

Managed Goal 的 Work Item 可以用 `single` 或 `phased` 作為內層 envelope。Goal status 與 side question 是 control/read-only request，不是新的 Managed Goal 工作。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {"execution_kind": "routed-work", "envelope": "phased"},
  "phases": ["design", "implement", "verify"]
}
```

<a id="failure-modes"></a>
## Failure modes

- 大型需求被迫塞進 `single` 時，會遺失 phase-specific capability 與 evidence checks。
- 小型 copy edit 被塞進 `managed-goal` 時，會產生不必要的 state 與 consent overhead。
- 跨 Phase 重用單一路由，會在工作改變後保留 stale capabilities。

<a id="security-boundary"></a>
## Security 與 authority boundary

Envelope classification 不授予 tool permission。每條 route 仍須通過 capability、risk、consent 與 host approval。Model 不能用「Goal mode」擴張 repository、production 或 communication authority。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_profiler tests.routing.test_explicit_skill_scenarios -v
```
