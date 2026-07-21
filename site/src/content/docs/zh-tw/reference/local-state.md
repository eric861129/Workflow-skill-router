---
title: 本機狀態
description: 了解 Router state 的位置、內容，以及 upgrade 對它的影響。
---

## 預設位置

| Platform | State root |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Codex\workflow-skill-router` |
| macOS | `~/Library/Application Support/Codex/workflow-skill-router` |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` |

設定 `WORKFLOW_SKILL_ROUTER_DATA_DIR` 可改用其他目錄。Runtime 會拒絕把 state path 放在 Plugin install/cache 邊界內。

## 儲存內容

Personal Routing Profile 放在相同外部資料根目錄下的 `profiles/personal/*.json`。Workspace Profile 仍由專案擁有，固定為 `.codex/workflow-skill-router.json`；MCP 模式還要求該 root 已由 Client 公告，或存在於 `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`。Profile 不放進 Plugin cache。

Profile 是 strict routing data，不是 executable instructions。已存在但無效的檔案會 fail closed；有效匹配也只是 `intended-unverified`，仍要由 Runtime Capability Discovery 檢查所選 SKILL。

Bundled local R0 會儲存 durable plan records、state versions、idempotency keys、workflow/work-graph IDs、envelope decisions 與 objective digests；local plan table 不會儲存明文 objective。Verified Host integration 可在不同 authority 下增加 event、projection、artifact 與 evaluation stores。

## Upgrade 與移除

state root 會解析到 Plugin 安裝／快取邊界之外。自動化的 local-root replacement 演練已驗證：保留這個外部路徑時，resolver 能持續找到相同的 state；但它不代表已驗證真實 `codex plugin remove` 後再重新安裝仍會保留 state。Windows/macOS/Linux 的完整生命週期驗證仍是尚未完成的 release-candidate migration evidence。

仍需要 audit history 或 resumable work 時，請保留這個外部 state path。進行 upgrade 或移除流程前，記錄明確路徑；在完成對應的生命週期證據前，請將任何 state 保留結果視為未驗證。

移除任何 state file 前，先停止 active Router processes，並確認沒有 Goal 依賴該狀態。只移除已檢查過的明確檔案或目錄；專案不會把 uninstall 視為靜默遞迴刪除的授權。

## 檢查 readiness

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

預設不啟用 telemetry。已設定的 model adapter 可能使用 provider quota；其 evidence 與 retention policy 必須另外揭露。
