---
title: 安裝到 Claude Code
description: 在 Claude Code 安裝、驗證與移除 Workflow Skill Router Plugin，並與 Codex 共用 Profile。
---

Claude Code 支援從 `v2.1.0` 開始提供，目前已發布的版本是 `v2.1.1`。下列 marketplace 指令會從 repository 的預設分支安裝 Plugin。

## 系統需求

- 支援 Plugin 的 Claude Code
- 啟動 Claude Code 的 `PATH` 上有 Node.js 24 以上
- Python 3.11 以上

Plugin 已包含 MCP bundle 與 Python runtime。它不附 `package.json`，所以 Claude Code 不會安裝任何 npm 套件。

## 從 marketplace 安裝

在 Claude Code 中執行：

```text
/plugin marketplace add eric861129/Workflow-skill-router
/plugin install workflow-skill-router@workflow-skill-router
```

也可以在 shell 執行：

```sh
claude plugin marketplace add eric861129/Workflow-skill-router
claude plugin install workflow-skill-router@workflow-skill-router
```

Plugin manifest 帶有產品版本號，版本改變時 Claude Code 就會提供更新。更新請執行 `claude plugin update workflow-skill-router@workflow-skill-router`。

## 載入開發 checkout

要測試 repository 變更但不安裝時，在 repository 根目錄指定 Plugin 目錄啟動 Claude Code：

```sh
claude --plugin-dir plugins/claude-code/workflow-skill-router
```

如果修改了 MCP server、Python core 或 canonical Skill 參考文件，請先執行 `python scripts/sync-claude-plugin.py`。CI 會用 `--check` 執行同一個腳本。

## 驗證

1. 執行 `/mcp`，確認 `plugin:workflow-skill-router:workflow-skill-router` 已連線。
2. 詢問 Claude Code：**「顯示 Workflow Skill Router 的狀態，並說明目前環境可以使用哪些能力。」** 回答應來自 `get_router_status`，並顯示 `bundled-local-r0`。
3. 離線檢查時，指定 host 執行內附 runtime。輸出必須包含 `"host": "claude-code"`。

```sh
WORKFLOW_SKILL_ROUTER_HOST=claude-code python plugins/claude-code/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

如果 `/mcp` 顯示 server 失敗，代表 Claude Code 無法啟動 Node.js，或 runtime 找不到 Python 3.11+。此時 SKILL 以 `skill-only-fallback` 運作，不能宣稱已保存狀態。

## Claude Code 與 Codex 的差異

| 項目 | Claude Code 的行為 |
| --- | --- |
| Host 設定 | Plugin 的 `.mcp.json` 設定 `WORKFLOW_SKILL_ROUTER_HOST=claude-code`。值不正確時，MCP server 會在讀取任何 workspace 檔案前停止。 |
| Workspace Profile | 先讀 `.claude/workflow-skill-router.json`，沒有時才讀 `.codex/workflow-skill-router.json`。Workspace Memory policy 也採同樣順序。 |
| 個人 Profile 與狀態 | 和 Codex Plugin 共用同一個外部資料目錄。仍可用 `WORKFLOW_SKILL_ROUTER_DATA_DIR` 覆寫。 |
| Native Goal | Claude Code 沒有 native Goal。Managed Goal 工作只使用 Router 自有的本機工作圖，並回報 `authority_mode=router-local`。 |
| 工具名稱 | `mcp__plugin_workflow-skill-router_workflow-skill-router__<tool>` |
| Workspace 信任 | Server 只讀取 MCP Client roots 或 `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS` 範圍內的 workspace 檔案。 |

同時用兩個 host 的 repository 可以只保留一份 `.codex/workflow-skill-router.json`。只有 Claude Code 需要不同的 Skill Tree 時，才另外加 `.claude/workflow-skill-router.json`。

## 移除

```sh
claude plugin uninstall workflow-skill-router@workflow-skill-router
```

Router 狀態存放在 Plugin cache 之外，移除後仍會保留 Profile、計畫與同意紀錄。刪除稽核紀錄前，請先閱讀[本機狀態說明](/Workflow-skill-router/zh-tw/reference/local-state/)。
