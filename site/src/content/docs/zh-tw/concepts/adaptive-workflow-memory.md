---
title: Adaptive Workflow Memory
description: 以選擇加入、本機優先的方式，將重複成功的路由經驗轉成可審查的知識。
---

Adaptive Workflow Memory 會把重複且成功的路由結果整理成可審查的規則，但它始終是 **default-off**。安裝 Plugin 或看到二十個 MCP 工具，不代表系統已開始蒐集資料、建立 Optional Memory DB、修改 Profile 或傳送遙測。

## 四種自主程度

| 模式 | Router 可以做什麼 | 明確不能做什麼 |
| --- | --- | --- |
| `disabled` | 回報 Memory 關閉。 | 不蒐集、不建立可選狀態。 |
| `observe` | 儲存符合條件且已去識別的本機觀察與型別化回饋。 | 不建立或套用 Profile 提案。 |
| `reviewed` | 產生 Candidate、Diff 預覽與 Backtest，等待明確核准。 | 未核准前不能套用。 |
| `automatic` | 只在明確啟動的本機 promotion pass 中，把高信心 `automatic-managed` Candidate 寫入 Router-managed Profile。 | 不修改 User-owned Profile、不繞過人工衝突，也不宣稱有背景排程。 |

自主程度固定為 `disabled < observe < reviewed < automatic`。Personal Policy 是上限；Workspace Policy 只能收緊目前工作區的權限，**Workspace cannot elevate Personal**。

## Profile 所有權不會被記憶功能改寫

```text
Explicit Skill Lock
-> User-owned Workspace Profile
-> Router-managed Workspace-local Profile
-> User-owned Personal Profile
-> Router-managed Personal Profile
-> Built-in routing
```

自動 promotion 只能寫入 `managed-personal` 或 `managed-workspace-local`。遇到人工 Profile 衝突時，Candidate 會被 suppression，不會覆寫 User-owned Profile，也不會偷偷改走其他路由。

## 從觀察到 Managed Rule

1. 已完成的 Router-owned workflow 只留下有界限的 observation，不保留 raw objective、secret 或 local path。
2. 回饋採 accepted、corrected、rejected 等型別化狀態；free text 需要額外雙重選擇加入。
3. 證據達門檻才形成 Candidate；R3、未知 Side-effect、未知 Skill 不會進入自動寫入。
4. `preview_profile_update` 只建立 Profile／Diff／Backtest 的精確綁定，不寫 Proposal 或 Profile。
5. 核准時重新驗證 Candidate、Policy、expected Profile 與 Backtest，再走 CAS、Revision、atomic write。
6. rollback 會建立新的 forward Revision，仍需審查，不會偷偷改寫歷史。

沒有 activation 或 receipt evidence 的 Skill 只能標示為 `intended-unverified`。**Skill consistency 在缺少 receipt evidence 時必須是 unavailable**，規劃意圖不能當成執行證明。

## 本機優先的隱私邊界

Operational DB 與 Optional Memory DB 分離。Memory 只使用 bounded ID、Digest、reason code 與聚合指標；維持 **no telemetry** 與 **no background learning**。匯出及 purge 都必須明確觸發。既有 purge scope 只刪除可選 history 或 analytics，保留 schema 與 User-owned Profile；purge 不等於刪除 Managed Profile。

`skill-only` 安裝只能說明 Policy，不能宣稱具備 durable Memory、MCP 審查 transition 或 Host-authorized Workspace write。需要完整能力時必須使用 Plugin + MCP runtime。


契約詞彙：`default-off`、`disabled < observe < reviewed < automatic`、
`Workspace cannot elevate Personal`、`automatic-managed`、`intended-unverified`、
`no telemetry`、`no background learning`、User-owned Profile、purge、`skill-only`，
以及建議順序 `observe -> reviewed -> automatic`。
