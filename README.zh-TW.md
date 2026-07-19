# Workflow Skill Router V2

[English](README.md) · [線上文件](https://huangchiyu.com/Workflow-skill-router/zh-tw/) · [Routing Flight Recorder](https://huangchiyu.com/Workflow-skill-router/zh-tw/#routing-flight-recorder)

Workflow Skill Router 是 Codex 的 runtime-aware 規劃與路由層。它讓 Agent 專注於最小且可驗證的執行路徑，保留使用者權限，並如實呈現 Runtime 真正能做的事。

> 目前版本：`2.0.0-beta.1`。V2 是公開產品主線；遷移期間仍可從 immutable V1.3.1 復原。

## 60-second outcome / 60 秒成果

把需求交給 Router，它會回傳 execution envelope、能力計畫、同意邊界，以及安全繼續工作所需的證據。公開 Flight Recorder 顯示真正經清理的 MCP request／response，不在瀏覽器重算決策。

```text
需求
  -> 判斷工作形狀
  -> 探索可用的 Runtime 能力
  -> 鎖定使用者明確指定
  -> 規劃最小路由
  -> 執行、驗證並揭露實際 SKILL 使用情形
```

## Plugin + MCP 與 Skill-only

| 能力 | Plugin + MCP | Skill-only |
| --- | --- | --- |
| 路由指令 | 內建 | 內建 |
| 本機 durable R0 規劃與 scoped consent | `plan_work`、`propose_support_consent`、`transition_support_consent`、`get_router_status` | 無法觀測 |
| verified-host 排程與 route validation | 完成 Host 整合後可用 | 不可用 |
| 跨程序狀態與 compare-and-swap | 取決於 Host／Runtime | 不可用 |
| sealed model evaluation | 需要 configured adapter | 只能人工執行 |
| 誠實的 Runtime 標籤 | `bundled-local-r0` 或 verified profile | `skill-only-fallback` |

Codex 支援 Plugin/MCP 時優先使用 Plugin。若 Host 不支援 Plugin，或只需要 instruction-only routing，再使用獨立 SKILL。Skill-only 絕不等於 `hybrid-full`。

## 五分鐘 Plugin + MCP quickstart

Contributor checkout：

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

immutable `v2.0.0-beta.1` tag 發布後，改用 tagged marketplace snapshot：

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
```

正式 Plugin 已包含 MCP bundle 與 Python runtime。執行需要 Node.js 24+ 與 Python 3.11+；只有從原始碼重建時需要 npm。完整說明請看 [Plugin 安裝](site/src/content/docs/zh-tw/guides/install-plugin.md)。

## 五分鐘 Skill-only quickstart

在 Windows contributor checkout 中執行：

```powershell
$Target = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Copy-Item -Recurse -Force "starter\v2\workflow-skill-router" $Target
Get-Content -Encoding UTF8 (Join-Path $Target "SKILL.md") | Select-Object -First 8
```

正式 Release 則將 `workflow-skill-router-skill-v2.0.0-beta.1.zip` 解壓至 Codex Skills 目錄。此套件保留路由指令與 explicit-choice policy，但無法證明 durable resume、完整 drift detection 或 sealed activation。完整說明請看 [Skill-only 安裝](site/src/content/docs/zh-tw/guides/install-skill.md)。

## 架構：先做 Runtime Capability Discovery

Runtime Capability Discovery 把常被混為一談的五個事實分開：已安裝 metadata、Host exposure、驗證狀態、policy eligibility 與 freshness。只有通過對應風險條件的能力才能進入路由。

```mermaid
flowchart LR
    U["使用者需求"] --> R["Router core"]
    H["Codex Host observations"] --> D["Runtime Capability Discovery"]
    P["Plugin handshake"] --> D
    S["SKILL metadata"] --> D
    D --> R
    R --> E["Single / Phased / Managed Goal"]
    E --> L["Local R0 control plane"]
    E --> V["Verified host adapters"]
    E --> M["Configured evaluation adapter"]
    V --> A["State、evidence 與 audit stores"]
```

Maintainer 可先閱讀 [V2 架構總覽](docs/architecture/v2-overview.md)。

## Single、Phased 與 Managed Goal

- **Single**：處理一個有明確邊界的意圖，只選最小 Primary capability。
- **Phased**：保留不同階段，並依當下證據為每個 Phase 重新路由。
- **Managed Goal**：維護可恢復的 Work Graph、尊重依賴關係，並把 Codex Goal 視為 Host-owned state。

Router 不會把每個任務都塞進 Goal 流程。工作形狀由需求、依賴、風險與目前 Goal relation 共同決定。

## Explicit Skill Lock

使用者指定 SKILL 時，該選擇具有權威性。Router 可以建議支援能力，但啟用前必須說明用途、scope、拒絕後果與 context cost。被拒絕的支援不得進入 active selections。

Plugin 模式會在詢問前先持久化 proposal。後續 model turn 只分類 `approved`、`rejected` 或 `unclear`；deterministic MCP transition 會保留 bound route，Phase、scope、revision 或 material context 改變時則 fail closed。Skill-only 仍保留相同互動政策，但只能宣稱 advisory instructions，不能宣稱 durable enforcement。

使用者未指定 SKILL 時，Router 直接選擇最小充分路由，不會為自己推薦的支援能力反覆詢問。執行前宣告預計使用的 SKILL，完成後回報實際使用項目與差異。

## MCP tool surface

Plugin 提供十二個 typed tools：

```text
sync_runtime_context       plan_work                  propose_support_consent
transition_support_consent get_next_work              validate_route
record_work_event          evaluate_gate              get_router_status
run_model_evaluation       compare_evaluations        export_router_artifact
```

Tool schema、risk、required capabilities 與 fallback actions 都從 Server 使用的相同 contract 產生。請看 [generated MCP reference](site/src/content/docs/zh-tw/reference/mcp-tools.mdx)。

## Runtime readiness matrix

| bundled local R0 可用性 | Tools | 意義 |
| --- | --- | --- |
| `local-ready` | `plan_work`、`propose_support_consent`、`transition_support_consent`、`get_router_status` | durable local R0 planning、scoped consent 與 status |
| `verified-host-required` | `sync_runtime_context`、`get_next_work`、`validate_route`、`record_work_event`、`evaluate_gate` | 需要 verified host authority 與 stores |
| `configured-adapter-required` | `run_model_evaluation`、`compare_evaluations`、`export_router_artifact` | 需要授權的 evaluation adapter 與 evidence |

不可用的呼叫會回傳 typed `capability-unavailable`、required capabilities 與 fallback action。Router 不會捏造 scheduler 或 evaluation 成功結果。

## Real Model Evaluation

**Tier 0 Contract** fixtures 只證明 deterministic compatibility，不是模型行為。Behavior evidence 需要 fresh isolated attempts、sealed case package、paired baseline/candidate manifests、bounded output、零 hard violation，以及公開前的可信任審查。Baseline arm 明確採 `model-only`，candidate 採 `hybrid-router`；consent follow-up 由 fresh model 分類 intent，再由持久化 MCP state machine 產生最終 route。

Evaluation contract `2.2.0` 已將目前 Phase oracle 與有狀態的 Phase-transition case 分開，將 scoped consent support 綁定到目前 Phase 的具體 exit evidence，並逐 turn 評分。六案例 beta profile 維持 36 attempts／42 model turns；十三案例 full gate 在每個 arm 重複三次時是 78 attempts／96 model turns。任何 `2.1.0` report 都只屬診斷證據，綁定舊 case 或 instruction digest 的 run 不得用新 oracle 事後重算。新的 `2.2.0` Behavior run 在授權執行前維持 `manual-required`，執行後則在可信 attestation 前維持 `review-required`。

## Security boundary 與 local state

Plugin 安裝、SKILL 同意、Runtime 權限與 production authorization 是不同決策。Model 不能提供 evaluation executable path、偽造 Host authority、把 fixture 升格成 runtime evidence，或直接修改 native Codex Goal。

Plugin 將 state 存在 cache 外：

| 平台 | 預設路徑 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Codex\workflow-skill-router` |
| macOS | `~/Library/Application Support/Codex/workflow-skill-router` |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` |

可用 `WORKFLOW_SKILL_ROUTER_DATA_DIR` 指定其他外部目錄。預設不啟用 telemetry。整合 Host-side R2/R3 行動前，先讀 [security boundary](site/src/content/docs/zh-tw/reference/security-boundaries.md)。

## Contributing

先讀 [CONTRIBUTING.md](CONTRIBUTING.md)，再針對修改範圍執行檢查。Release artifacts 由 allowlist 與 deterministic builder 產生，不手動修改 generated outputs。

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/build-v2-demo-data.py --check
$Version = (Get-Content -Raw -Encoding UTF8 release/version.json | ConvertFrom-Json).v2_version
$Output = Join-Path "dist" "release-$Version"
python scripts/build-release-artifacts.py --output-dir $Output --provenance-mode test --check-determinism
```

Release builder 只允許覆寫目前 manifest 內的既有產物。如果 output directory 含有 stale、非預期、symlink 或其他未列入 manifest 的 path，會直接 fail closed；請使用版本專屬目錄，不要混放不同 release generation。

## Version channels

| Channel | 目前用途 | Promotion rule |
| --- | --- | --- |
| `latest` | V2 GA 前維持 V1.3.1 compatibility | 通過 GA release gate 後才移動 |
| `latest-v1` | immutable V1 recovery | 固定 V1.3.1 |
| `latest-v2` | V2 alpha/beta prerelease | 追蹤已審查的 V2 prerelease |

即使 compatibility channel 尚未移動，Repository 的產品方向仍是 V2-first。版本 metadata 位於 [`release/version.json`](release/version.json)。

## V1 migration

使用 [V1 到 V2 遷移指南](site/src/content/docs/zh-tw/guides/migrate-v1-to-v2.md)，從 template-based routing 遷移至 runtime-aware Plugin 或獨立 SKILL。V1 原始碼與套件仍可從 immutable [`v1.3.1` tag](https://github.com/eric861129/Workflow-skill-router/tree/v1.3.1) 與 GitHub Release 復原，但不再放在 V2 primary navigation。

MIT License。
