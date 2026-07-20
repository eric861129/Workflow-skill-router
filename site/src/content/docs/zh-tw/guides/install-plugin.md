---
title: 安裝 Plugin + MCP Runtime
description: 安裝、驗證與移除 Workflow Skill Router V2 Plugin，同時如實呈現本機能力。
---

## 系統需求

- 支援 Plugin 與 MCP 的 Codex
- Python 3.11 以上
- Node.js 24 以上

發行壓縮檔已包含 MCP bundle 與 Python runtime；只有從原始碼重新建置時才需要 npm。

## 從已標記的 marketplace snapshot 安裝

一般安裝請使用已發布且不可變的 `v2.0.0-beta.1` snapshot：

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.0-beta.1
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Plugin registration 變更後，請重新啟動 Codex 或開啟新任務。要求 Codex 顯示 Workflow Skill Router 狀態；回應應標示 `bundled-local-r0`，並能看到 Router MCP tools。

## 從開發 checkout 安裝

只有開發或測試 repository 變更時，才使用 checkout：

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

## 從原始碼或解壓縮 ZIP 深入驗證

下列指令在 repository checkout 執行。若要檢查 Release ZIP，請將 `path/to/extracted/workflow-skill-router` 換成解壓縮後的 Plugin 目錄：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
node plugins/workflow-skill-router/scripts/smoke-plugin.mjs path/to/extracted/workflow-skill-router
```

`doctor` 必須顯示 `bundled-local-r0`、停用 telemetry，以及每個 tool 的 readiness matrix。解壓縮後的 smoke test 會驗證 manifest、canonical SKILL、十二個 tool 名稱、外部 state 邊界，以及真實 MCP initialize/tools-list 交換。

## 本機可用範圍

`plan_work`、`propose_support_consent`、`transition_support_consent` 與 `get_router_status` 是 local-ready。排程、受保護 route 驗證、work event 與 gate 都需要經 Host 驗證的能力；模型評測工具需要已設定 adapter。不可用的呼叫會回傳 `capability-unavailable`，並列出需求與 fallback。

## 移除

```powershell
codex plugin remove workflow-skill-router@workflow-skill-router
```

移除 Plugin 不會刪除外部 Router state。移除 audit history 前，先閱讀[本機狀態](/Workflow-skill-router/zh-tw/reference/local-state/)說明。
