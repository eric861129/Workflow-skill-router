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

一般安裝請確認 marketplace 固定在 `v2.0.0-beta.2`，重新安裝 `workflow-skill-router@workflow-skill-router`，再重新啟動 Codex。使用 contributor checkout 時，請先確認 marketplace 指向 repository root。

## 純 SKILL 沒有觸發

確認目錄第一層直接包含 `SKILL.md`：

```powershell
$Router = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Test-Path (Join-Path $Router "SKILL.md")
Get-Content -Encoding UTF8 (Join-Path $Router "SKILL.md") | Select-Object -First 8
```

安裝後開啟新任務。純 SKILL 必須宣告 `skill-only-fallback`；它無法自行暴露 MCP tools。

## Tool 回傳 `capability-unavailable`

這是有型別、可預期的結果。閱讀 `runtime_requirement`、`required_capabilities` 與 `fallback_action`。不要虛構 Host authority，也不要把 tool 改標成 local-ready。`get_next_work`、受保護 route 驗證、events 與 gates 需要 verified Host ports；evaluation tools 需要 configured adapter。

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
