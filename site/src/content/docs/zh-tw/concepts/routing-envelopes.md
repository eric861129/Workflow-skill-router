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

結構分析器會記錄 `classifier_revision: deterministic-objective-v1`、`classification_source` 與 `classification_reason_codes`。它只分析階段、依賴與可續作性等有界結構訊號，不宣稱能理解所有工作的語意；分類也絕不授權 Skill、工具或 side effect。Semantic adapter 可以提出供審查的候選結果，但不能直接改寫已持久化的路由。

<a id="example"></a>
## State、input 與 output 範例

```json
{
  "signals": {"distinct_stages": 3, "dependency_edges": 2, "resumable": false},
  "decision": {
    "execution_kind": "routed-work",
    "envelope": "phased",
    "classifier_revision": "deterministic-objective-v1",
    "classification_source": "deterministic-analyzer",
    "classification_reason_codes": ["multiple-distinct-stages"]
  },
  "phases": ["design", "implement", "verify"]
}
```

<a id="runtime-readiness"></a>
## Runtime readiness

### 已發布 beta.3（`published-beta.3`）

| 目前類別 | 工具 | 意義 |
| --- | --- | --- |
| `local-ready`（4） | `plan_work`、`propose_support_consent`、`transition_support_consent`、`get_router_status` | bundled R0 支援其文件定義的 Router-local 範圍。 |
| `verified-host`（5） | `sync_runtime_context`、`get_next_work`、`validate_route`、`record_work_event`、`evaluate_gate` | 必須具備經驗證的 Host 狀態、政策與 receipt；本機呼叫會 fail closed。 |
| `configured-adapter`（3） | `run_model_evaluation`、`compare_evaluations`、`export_router_artifact` | 必須具備伺服器端設定的 adapter、授權與適用的 attestation。 |

### 已準備的 beta.5 candidate（`prepared-beta.5-candidate`）

此 candidate 已實作 `conditional-local` work，但它 **not included in published beta.3**，也不代表 beta.5 已發布。它維持 `prepared-local-candidate` lifecycle；後續受信任的 metadata-only promotion 必須把 `release_source_revision` 綁定到這個 exact reviewed candidate SHA，才可 dispatch。

| Source 類別 | 工具 | 此 checkout 中的意義 |
| --- | --- | --- |
| `local-ready`（4） | `plan_work`、`propose_support_consent`、`transition_support_consent`、`get_router_status` | 維持既有 Router-local R0 操作。 |
| `conditional-local`（3） | `get_next_work`、`record_work_event`、`evaluate_gate` | 僅限 Router 自有 work graph 與本機 advisory evidence；輸出使用 `authority_mode=router-local` 與 `host_transition_authorized=false`。 |
| `verified-host`（2） | `sync_runtime_context`、`validate_route` | Host 權威仍為必要條件。 |
| `configured-adapter`（3） | `run_model_evaluation`、`compare_evaluations`、`export_router_artifact` | configured-adapter 權威仍為必要條件。 |

Host 權威狀態使用獨立的 `authority_mode=verified-host`；設定式評估使用 `authority_mode=configured-adapter`。GA 並不代表 12 項工具全部可在本機使用。

Conditional boundary 會依工具與情況分開處理：

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
- 在已發布 beta.3 中，本機呼叫 `get_next_work`、`record_work_event` 或 `evaluate_gate` 仍需要 verified Host。
- 在尚未發布的 source checkout 中，Native Goal work 依各工具的 verified Host capability fail closed，且不修改原生 Codex Goal。
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
