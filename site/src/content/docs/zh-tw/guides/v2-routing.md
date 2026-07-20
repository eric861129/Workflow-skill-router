---
title: V2 路由與 Goal 編排
description: Single、Phased、Managed Goal、Explicit Skill Lock 與同意邊界。
---

# V2 路由

## 帶入自己的 Skill Tree

當次請求沒有指定 SKILL 時，`plan_work` 可套用 Personal Routing Profile。Strict JSON contract 會依 objective keywords、domains、tags 與 work modes 對應 phased Skill Tree。Workspace 規則高於 personal；Router 採用一棵完整 tree，不會 deep merge 兩者。

Profile output 是 `intended-unverified`。Runtime Capability Discovery 仍控制 activation，使用者當次明確指定 SKILL 也永遠高於 Profile。使用新規則前先跑 `profile preview`。Skill-only 依相同政策做 advisory `skill-only-fallback`，而且必須有 Host filesystem access 才能讀取固定的本機 Profile。Personal Routing Profiles 隨 `v2.0.0-beta.2` 提供。

Router 先判斷 Goal relation，再選 **Single**、**Phased** 或 **Managed Goal**。每個 Phase 與 Goal Work Item 都會獨立重新路由。

使用者未指定 SKILL 時，Router 會自動選擇最小必要的 Primary／Supporting 組合，不再為自己的推薦逐次詢問。只有使用者指定 SKILL 時才啟用 Explicit Skill Lock；指定集合外的輔助能力必須先說明用途與 scope，未取得 consent（同意）前不可讀取。

Router 會在執行前宣告預計使用的 SKILL，完成後列出實際使用項目。`skill-only-fallback` 會揭露 durable 保證不足；Plugin 的本機 R0 control plane 可持久化 `plan_work`，但 `hybrid-full` 仍必須完成 preflight，R2/R3 仍需 host approval。

80 個案例是 **Tier 0 Contract**。沒有真實 adapter 時，Behavior 評測會回 `manual-required`。
