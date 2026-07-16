---
title: V2 路由與 Goal 編排
description: Single、Phased、Managed Goal、Explicit Skill Lock 與同意邊界。
---

# V2 路由

Router 先判斷 Goal relation，再選 **Single**、**Phased** 或 **Managed Goal**。每個 Phase 與 Goal Work Item 都會獨立重新路由。

Explicit Skill Lock 貫穿三種 envelope；輔助能力必須先說明用途與 scope，未同意前不可讀取。`skill-only-fallback` 會揭露 durable 保證不足，`hybrid-full` 必須完成 preflight；R2/R3 仍需 host approval。

80 個案例是 **Tier 0 Contract**。沒有真實 adapter 時，Behavior 評測會回 `manual-required`。
