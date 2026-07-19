---
title: CLI Reference
description: 檢查 runtime readiness、啟動 JSONL bridge，並準備已授權的 evaluation run。
---

## Entrypoint

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz --help
```

Commands 包括 `serve-jsonl`、`doctor`、`status`、`plan`、`validate-route` 與 `evaluation`。MCP server 使用 `serve-jsonl`；直接操作時應先執行 `doctor`。

## Runtime readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

JSON output 會列出 active runtime profile、telemetry 狀態、content preflight 可見度，以及每個 public tool 的 readiness。

## Plan 與 status

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz plan --help
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz status --help
```

這些 commands 使用外部 local state database。在 verified integration 提供對應 ports 前，受保護的 Host 行為仍不可用。

## Evaluation

Dry-run manifest 不會消耗 quota。Behavior/Outcome subprocess run 需要 trusted operator configuration 提供絕對 executable path，並明確加上 `--confirm-live-run`：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz evaluation run --help
```

不要把 model output 提供的 executable path 直接放入已授權的執行。先閱讀 [evaluation evidence contract](/Workflow-skill-router/zh-tw/concepts/evaluation-evidence/)。
