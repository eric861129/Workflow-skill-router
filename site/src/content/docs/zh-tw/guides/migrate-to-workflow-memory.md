---
title: 遷移至 Workflow Memory
description: 以漸進方式導入 Adaptive Workflow Memory，不改變既有路由所有權。
---

既有安裝升級後仍維持 **default-off**。在啟用 Policy 且真正進入寫入操作前，不修改 User-owned Profile，也不建立 Optional Memory DB。

## 1. 建立乾淨基準

更新 Plugin、執行 `memory status`、驗證 Personal／Workspace Policy，並只匯出審查需要的 public-safe metadata。保留既有 Personal Routing Profile；Memory 是額外的 managed layer，不是替代品。

## 2. 先 Observe

先啟用 `observe`。確認只有符合條件的 Router-owned completion 進入記錄，R3 與未知 Side-effect 被排除，raw objective、path、secret 不會出現。檢視 aggregate metrics 與 correction rate。沒有 activation receipt 時維持 `intended-unverified`；缺少 receipt evidence 時 Skill consistency 必須為 unavailable。

## 3. 審查 Proposal

樣本具代表性後才切換 `reviewed`。逐一查看 Candidate evidence、精確 Profile Diff 與 Backtest；核准必須綁定同一份 preview。拒絕只 suppression 未變更的 evidence，不寫 Profile，也不改走 fallback。

## 4. 評估 Automatic Managed Promotion

多次 reviewed approval 都乾淨後，才考慮 `automatic`。自主順序為 `disabled < observe < reviewed < automatic`，且 **Workspace cannot elevate Personal**。自動寫入必須是 `automatic-managed`，target 只允許 `managed-personal`、`managed-workspace-local`；人工衝突會 suppression Candidate。

Automatic promotion 仍是明確觸發的本機 pass，必須顯示 notification，維持 **no background learning**、沒有 scheduler、沒有 telemetry；Runtime 與 Side-effect authority 不會因此提升。

## 5. 演練 Rollback 與 Purge

Rollback 會建立新的 reviewable forward Revision 並保留歷史。Purge 必須明確確認並綁定目前 Digest；history／analytics purge 不刪除 User-owned Profile。將模式改回 disabled 只停止後續 capture，不會暗中清除既有資料。

## 建議順序

採用 `observe -> reviewed -> automatic`，每次 transition 都保留人工 checkpoint。若 evidence、privacy 或 ownership 假設失效，立即回到 `disabled`。

`skill-only` 可以用本指南準備設定，但不能宣稱 durable Memory 或 MCP review transition；操作流程需要 Plugin + MCP。維持 **no telemetry**。


契約詞彙：`default-off`、`disabled < observe < reviewed < automatic`、
`Workspace cannot elevate Personal`、`automatic-managed`、`intended-unverified`、
`no telemetry`、`no background learning`、User-owned Profile、purge、`skill-only`，
以及建議順序 `observe -> reviewed -> automatic`。
