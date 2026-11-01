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

Managed Goal 的 Work Item 可以用 `single` 或 `phased` 作為內層 envelope。分類順序固定如下：

1. 先把 Goal status 與 side question 判定為控制／唯讀請求，而不是新的執行工作。
2. 原生 Goal progress 或 steer 決定外層 `managed-goal` envelope。
3. 對獨立請求或目前 Work Item，依序由 `requested_work_mode`、deterministic analyzer、deterministic Profile route 與 builtin fallback 選擇內層 envelope。

結構分析器會記錄 `classifier_revision: deterministic-objective-v2`、`classification_source` 與 `classification_reason_codes`。它只分析階段、依賴與可續作性等有界結構訊號，不宣稱能理解所有工作的語意；分類也絕不授權 Skill、工具或 side effect。Semantic adapter 可以提出供審查的候選結果，但不能直接改寫已持久化的路由。

目前 `deterministic-objective-v2` 增加「修復／修正」「釐清需求」「跨專案」「保留進度」等結構訊號，並排除否定的長期工作訊號。既有紀錄保留建立時的分類版本，重播不重新分類。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {
    "execution_kind": "routed-work",
    "envelope": "phased",
    "classifier_revision": "deterministic-objective-v2",
    "classification_source": "deterministic-analyzer",
    "classification_reason_codes": ["multiple-distinct-stages"]
  },
  "phases": ["design", "implement", "verify"]
}
```

<a id="runtime-readiness"></a>
## Runtime readiness

### 前一版（`published-v2.0.2`）

`v2.0.2` 有 12 個工具：**4 always local-ready + 3 Router-owned conditional-local**、2 個 verified-Host-required，以及 3 個 configured-adapter-required。發布版已包含本機工作迴圈，但不包含後續的 Adaptive Workflow Memory。

### v2.1.x 與開發中主分支（`development-main`）

`v2.1.0` 增加 8 個 Memory 工具，合計 20 個；Memory 預設關閉。下表描述 `v2.1.1` 與目前原始碼。

| Availability | Tools | 條件 |
| --- | --- | --- |
| `local-ready` (10) | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status`, `get_memory_status`, `remember_workflow`, `record_route_feedback`, `list_workflow_candidates`, `preview_profile_update`, `purge_workflow_memory` | 本機工具仍須通過個別輸入、Policy 與確認條件；local-ready 不等於所有副作用都已獲准。 |
| `conditional-local` (5) | `get_next_work`, `record_work_event`, `evaluate_gate`, `transition_profile_update`, `rollback_profile_revision` | 依工具檢查 Router 自有工作圖或受 Policy 約束的本機 Profile；本機工作迴圈回傳 `authority_mode=router-local`。`get_next_work` 回傳 `host_goal_mutated=false`；事件與閘門呼叫則回傳 `host_transition_authorized=false`。 |
| `verified-host-required` (2) | `sync_runtime_context`, `validate_route` | 必須具備已驗證的 Host 權威。 |
| `configured-adapter-required` (3) | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | 必須具備已設定的評估介面與授權。 |

| 情況 | `get_next_work` | `record_work_event` | `evaluate_gate` |
| --- | --- | --- | --- |
| 有效 Router-owned graph | Router-local 結果 | Router-local 回報 | Router-local advisory gate |
| Native Goal | `verified-host-scheduler` | `verified-event-store` + `activation-receipt-verifier` | `verified-evidence-store` + `gate-authority` |
| 缺少 graph | `router-owned-work-graph`；在本機建立或 replay | `router-owned-work-graph`；在本機建立或 replay | `router-owned-work-graph`；在本機建立或 replay |
| Graph 損毀 | 已清理的 `internal-error` | 已清理的 `internal-error` | 已清理的 `internal-error` |

<a id="failure-modes"></a>
## Failure modes

- 大型需求被迫塞進 `single` 時，會遺失 phase-specific capability 與 evidence checks。
- 小型 copy edit 被塞進 `managed-goal` 時，會產生不必要的 state 與 consent overhead。
- 跨 Phase 重用單一路由，會在工作改變後保留 stale capabilities。
- 在 `v2.0.2`、`v2.1.0`、`v2.1.1` 與開發中主分支中，Native Goal work 依各工具的 verified Host capability fail closed，且不修改原生 Codex Goal。
- 缺少 Router-owned graph 時要求在本機建立或 replay，不會捏造 Host 路徑。
- Graph 損毀時只回傳已清理的 `internal-error`，損毀細節留在內部 diagnostics。
- Router-local gate 通過只代表 advisory gate，不會啟用 Skill、不會授權原生 Goal transition，也不會授予部署或正式環境權限。
- 缺少必要 receipt、configured adapter、consent 或 Explicit Skill Lock 條件時，受保護的操作不會執行。

<a id="security-boundary"></a>
## Security 與 authority boundary

Envelope classification 不授予 tool permission。每條 route 仍須通過 capability、risk、consent、Explicit Skill Lock 與 Host approval。Router-local 狀態不會宣稱 Skill 已啟用，也不會改動原生 Goal。Model 不能用「Goal mode」擴張 repository、deployment、production 或 communication authority。

<a id="verify"></a>
## 驗證

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
Set-Location packages/router-core
$env:PYTHONPATH = (Resolve-Path src).Path
python -m unittest tests.routing.test_profiler tests.routing.test_explicit_skill_scenarios -v
```
