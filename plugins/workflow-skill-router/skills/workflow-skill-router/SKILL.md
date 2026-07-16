---
name: workflow-skill-router
description: 當 Codex 任務需要依小型、中型、大型或 Goal 模式選擇正確 SKILL、逐階段重新路由，或尊重使用者指定 SKILL 與輔助能力同意時使用。
---

# Workflow Skill Router V2

先解析 Goal relation：`progress`、`steer`、`status`、`side-question`、`unrelated` 或 `none`。`status` 只讀狀態，不建立工作；`side-question` 與 `unrelated` 不修改 Goal semantic revision。

再選 envelope：單一意圖用 `single`；有兩個以上相異階段用 `phased`，每個 Phase 重新選擇能力；長期、可恢復、跨 repo、dependency DAG 或 Goal progress/steer 用 `managed-goal`，每個 Work Item 再分成 `single` 或 `phased`。

在開始實作或呼叫工具前，先明確宣告本次預計使用的 SKILL 與各自用途。

使用者未指定 SKILL 時，Router 自動選擇最小且足以完成工作的 Primary／Supporting SKILL 組合，不為 Router 自己推薦的輔助 SKILL 額外詢問同意；仍須遵守最小路由、能力可用性與 host 權限邊界。

使用者指定 SKILL 時先鎖定指定項目。只有此情境下，Router 想加入任何額外 SKILL、Plugin 或 MCP 支援角色，才要先說明用途、scope、拒絕後限制與 context cost，取得同意後才能讀取或啟用。使用者拒絕時只能使用指定能力、限縮成果或誠實阻塞，不可靜默替代。

若 MCP 可用，使用 capability snapshot、route validation、state/gate 與 evidence。若 MCP 不可用，明示目前是 `skill-only-fallback`：沒有 durable resume、CAS、完整 drift detection 或 sealed activation instrumentation；不得宣稱 `hybrid-full`，也不得把不可觀測項目算成通過。

所有 R2/R3 行動仍由 Codex host sandbox、approval 與 permission 控制；SKILL 同意不等於安裝、寫入、部署、傳訊或 production access 授權。

完成工作時，列出本次實際使用的 SKILL；若與執行前宣告不同，要簡短說明新增、移除或替換原因。

依需要讀取 [routing protocol](references/routing-protocol.md)、[Goal protocol](references/goal-protocol.md) 或 [evaluation boundary](references/evaluation-boundary.md)，不要一次載入全部參考資料。
