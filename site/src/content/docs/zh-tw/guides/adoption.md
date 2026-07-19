---
title: 在既有團隊導入 V2
description: 導入 runtime-aware routing，同時不取代 Host authority，也不強迫每個需求都使用 Goal。
---

## 先定義操作邊界

Workflow Skill Router 只負責選擇 routing envelope 與最小、合理的 SKILL 組合。它不授予 tool access、不核准 side effects、不取代 Codex Goal state，也不會讓已安裝的 capability 自動變成可用。Host permissions、approvals 與 deployment controls 仍是權威來源。

## 選擇 rollout surface

| 環境 | 起始方式 | 升級時機 |
| --- | --- | --- |
| 支援 Plugin/MCP | Plugin + MCP | verified Host integration 已準備完成 |
| 只有 instructions | 純 SKILL fallback | 環境開始支援 Plugin |
| 既有 V1 router | 在新任務並行試跑 V2 | 代表性 routes 通過 review |

不要把純 SKILL 標示成 `hybrid-full`；它是保證邊界較小、但明確受支持的 fallback。

## 建立有證據的 inventory

在 runtime 發現 capabilities，再依 authority 合併 observations。Installation、Host exposure、authorization、policy eligibility、freshness 與 risk 必須分開判斷。本機有檔案或 cache observation，不代表 tool 此刻可執行。

## 校準三種 envelopes

- `single`：範圍明確，能在一次執行中完成並驗證。
- `phased`：跨越不同階段或 verification boundaries。
- `managed-goal`：需要 resumable dependency graph、durable progress 與明確 completion criteria。

需求文字很長不代表一定要用 Goal；應由 complexity、dependencies、resume needs 與 state transitions 決定。

## 保留使用者選擇

使用者沒有指定 SKILL 時，自動選擇最小集合，不要增加多餘 consent ceremony。使用者明確指定 SKILL 時，鎖定該選擇；lock 外的輔助建議在使用者接受前都保持 inactive。

工作開始前宣告預計使用的 SKILL；完成時揭露實際使用、略過，以及經同意後加入的技能。

## 從 pilot 擴大

建立小型測試組，涵蓋 automatic single routing、phased work、explicit lock 接受與拒絕、Managed Goal degradation，以及 unavailable capability。先審查 Flight Recorder 的 evidence shape，再只針對實際觀察到的失敗增加團隊 policy。

下一步：[V1 遷移](/Workflow-skill-router/zh-tw/guides/migrate-v1-to-v2/)與[安全邊界](/Workflow-skill-router/zh-tw/reference/security-boundaries/)。
