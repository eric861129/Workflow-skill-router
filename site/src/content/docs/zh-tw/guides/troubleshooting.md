---
title: V2 疑難排解
description: 診斷安裝、runtime readiness、routing、state 與 evaluation 問題，同時維持安全邊界。
---

## 先執行 `doctor`

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

確認 runtime profile、telemetry 狀態、Python 版本、content preflight 結果、state path 與每個 tool 的 readiness。`bundled-local-r0` 如實代表 local planning 與 status，不是完整 Host orchestration。

## Plugin 沒有出現

```powershell
codex plugin list
```

一般安裝請確認 marketplace 固定在 `v2.0.1`，重新安裝 `workflow-skill-router@workflow-skill-router`，再重新啟動 Codex。使用 contributor checkout 時，請先確認 marketplace 指向 repository root。

## Plugin 啟動失敗

若錯誤指出 Python Runtime 無法使用、MCP 伺服器無法啟動，Plugin 不會自動切換為純 SKILL 模式。請在啟動錯誤後自行安裝或選擇獨立的純 SKILL 模式。

此訊息只代表已確認的 Python discovery 失敗；單憑 OS spawn error 並不能證明 Python 無法使用。

若錯誤改為指出 MCP 啟動失敗，應視為本機 state path、檔案系統權限或 Plugin 安裝問題，而不是 Python 診斷。請檢查設定的本機 state directory、其權限與 Plugin 安裝後再重試。

Runtime 在啟動後當掉時，該 bridge generation 內的 request 會回傳錯誤，且可能需要重試；這不代表提供高可用性保證。

## 純 SKILL 沒有觸發

確認目錄第一層直接包含 `SKILL.md`：

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path (Join-Path $Router "SKILL.md")
Get-Content -Encoding UTF8 (Join-Path $Router "SKILL.md") | Select-Object -First 8
```

安裝後開啟新任務。純 SKILL 必須宣告 `skill-only-fallback`；它無法自行暴露 MCP tools。

## Tool 回傳 `capability-unavailable`

這是有型別、可預期的結果。閱讀 `runtime_requirement`、`required_capabilities` 與 `fallback_action`。不要虛構 Host authority，也不要把 tool 改標成 local-ready。

在尚未發布的 source checkout 中，只有已驗證的 Router-owned graph 存在、且沒有 Native Goal authority 時，`get_next_work`、`record_work_event` 與 `evaluate_gate` 才可走 `conditional-local`。它們分別回傳 Router-local 排程、回報式本機進度或 advisory local gate；不會驗證 Skill activation，也不會授權 Host transition。Graph 缺少時回傳 `router-owned-work-graph`，呼叫端應建立或 replay 本機 graph；graph 損毀時則只回傳已清理的 `internal-error`，絕不捏造 Host fallback。Native Goal 工作改用各工具所需的 verified-host capabilities。

`validate_route` 在所有分支都維持 `verified-host-required`。`sync_runtime_context` 也需要 verified Host authority；evaluation tools 則需要 configured adapter。

## Explicit Skill Lock 詢問太頻繁

只有當使用者明確指定 SKILL，而且 Router 建議 lock 外的輔助技能時，才需要 consent。使用者沒有指定 SKILL 時，Router 應自動選擇最小合理集合，並在執行前宣告。

## State 或 resume 問題

檢查 `WORKFLOW_SKILL_ROUTER_DATA_DIR` 與[本機狀態](/Workflow-skill-router/zh-tw/reference/local-state/)列出的平台預設位置。放在 Plugin install/cache boundary 內的 state directory 會被拒絕。檢查或移除已審查的 state file 前，先停止 active Router processes。

## Evaluation 無法執行

Live execution 需要 operator-configured absolute executable path 與 `--confirm-live-run`。Dry-run 或 fixture 都不是 Behavior evidence。修正後的 live run 也需要明確 quota authorization；不得重試舊的 superseded run，然後把它宣稱為目前證據。

## Site 或 docs 驗證失敗

```powershell
python scripts/check-doc-parity.py
python scripts/check-markdown-links.py .
node scripts/build-mcp-reference-data.mjs --check
Set-Location site
npm run build
```

應修正 source contracts 或 source docs，不可手動編輯 generated MCP reference data 或 release archives。

## 回報 issue

提供作業系統、runtime profile、完整 command、已去識別化 error，以及使用 Plugin 或純 SKILL。排除 tokens、raw model traces、private paths、customer names 與 internal repository data。
