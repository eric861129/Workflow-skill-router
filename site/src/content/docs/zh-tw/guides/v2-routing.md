---
title: V2 路由與 Goal 編排
description: Single、Phased、Managed Goal、Explicit Skill Lock 與同意邊界。
---

# V2 路由

Router 先判斷 Goal relation，再選 **Single**、**Phased** 或 **Managed Goal**。每個 Phase 與 Goal Work Item 都會獨立重新路由。

使用者未指定 SKILL 時，Router 會自動選擇最小必要的 Primary／Supporting 組合，不再為自己的推薦逐次詢問。只有使用者指定 SKILL 時才啟用 Explicit Skill Lock；指定集合外的輔助能力必須先說明用途與 scope，未取得 consent（同意）前不可讀取。

Router 會在執行前宣告預計使用的 SKILL，完成後列出實際使用項目。`skill-only-fallback` 會揭露 durable 保證不足；Plugin 的本機 R0 control plane 可持久化 `plan_work`，但 `hybrid-full` 仍必須完成 preflight，R2/R3 仍需 host approval。

80 個案例是 **Tier 0 Contract**。沒有真實 adapter 時，Behavior 評測會回 `manual-required`。
