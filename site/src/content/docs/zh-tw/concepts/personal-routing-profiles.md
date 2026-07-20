---
title: Personal Routing Profiles
description: 保留使用者自訂 Skill Tree，同時讓 Runtime Capability Discovery 守住真實啟用邊界。
---

Personal Routing Profile 把個人偏好的工程流程變成 deterministic routing data。它保留 V1「使用者擁有 Skill Tree」的精髓，但不會退回靜態 catalog，也不會假設每個 SKILL 都可用。

這份 contract 屬於 `v2.0.0-beta.2`。beta.1 已發布的 36-attempt Model Evaluation 不涵蓋 Personal Routing Profiles；本功能目前只有 deterministic contract、integration、security 與 package evidence。

## 使用者可以定義什麼

每條 rule 可依 objective keywords、domains、tags 或 work modes 匹配。Route 選擇 `single`、`phased` 或 `managed-goal`，再為每個 Phase 定義一個 Primary、最多三個 immediate support SKILL，以及一個 exit gate ID。

```json
{
  "schema_id": "workflow-skill-router/routing-profile",
  "schema_version": "1.0.0",
  "artifact_kind": "routing-profile",
  "profile_id": "personal:api-delivery",
  "scope": "personal",
  "enabled": true,
  "rules": [{
    "rule_id": "api-delivery",
    "priority": 100,
    "match": {
      "objective_keywords": ["api", "openapi"],
      "domains": ["api"],
      "tags": [],
      "work_modes": []
    },
    "route": {
      "work_mode": "phased",
      "skill_tree": [{
        "phase_id": "contract",
        "primary_skill_id": "skill:api-designer",
        "support_skill_ids": ["skill:api-guidelines-skill"],
        "exit_gate": "contract-reviewed"
      }]
    }
  }]
}
```

獨立 SKILL 套件內附兩份完整三階段範例：`assets/personal-routing-profile.example.json` 與 `assets/workspace-routing-profile.example.json`。

## 不製造意外路由的優先序

固定順序如下：

1. System、developer、safety 與 Host hard constraints。
2. 使用者在當次請求明確指定的 SKILL。
3. Workspace Profile。
4. Personal Profile。
5. Built-in routing。

簡寫是 `workspace > personal > built-in`，但使用者當次明確指定永遠高於所有 Profile。Workspace 與 personal 同時匹配時，Router 採用完整 workspace tree，不 deep merge 成使用者從未定義過的混合 route。

## 安裝與 preview

Workspace Profile 放在 `.codex/workflow-skill-router.json`。請使用 `assets/workspace-routing-profile.example.json`，它的 identity 欄位是：

```json
{
  "profile_id": "workspace:api-delivery",
  "scope": "workspace"
}
```

不要把 personal 範例原樣複製到 workspace；`.codex/workflow-skill-router.json` 若仍是 `scope: personal` 會 fail closed。Personal Profile 安裝到 Router 外部資料目錄：

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "交付 API" --work-mode phased --domain api
```

`plan_work` 可接收 optional `routing_context`：`workspace_root`、`domains`、`tags`、`current_phase_id`。既有 beta.1 caller 可以省略。只有目前 Phase 的 Primary 與 immediate support 會進入 `planned_skill_ids`；完整 tree 只作規劃資料。

MCP 模式下，`workspace_root` 必須位於 Client 公告的 root，或維護者透過 `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS` 明確設定的 root 之內。只有一個 Client root 時，Plugin 會替省略 `routing_context` 的舊 caller 綁定該 root；多個 roots 則必須明確選擇其中一個。模型任意提供的其他本機路徑會回 `workspace-root-untrusted`，而且不會被開啟。

## Runtime Capability Discovery 仍決定是否可啟用

Profile 命中只會得到 `intended-unverified`。Runtime Capability Discovery 仍檢查 presence、exposure、compatibility、authentication、policy eligibility 與 freshness。若 intended SKILL 不可用，Router 保留原 intended ID 並誠實回報 limitation，不會靜默換成其他 SKILL。

Profile 是資料，不是 instructions。Strict contract 會拒絕 `instructions` 等未知欄位、executable paths、shell、權限或任意 agent directives。已存在但無效的 Profile 會 fail closed，不會從 decision trace 中消失。

## Plugin + MCP 與 Skill-only

Plugin + MCP 會 deterministic 載入、驗證、解析、持久化與 preview Profile，並把 personal profiles 放在 Plugin cache 之外。

Skill-only 只有在 Host 授權讀取 workspace 與 Router data directory 時，才能讀取相同固定位置；否則必須由使用者在對話中明確提供 Profile 內容。結果只是 advisory `skill-only-fallback`，不能宣稱 durable loading、compare-and-swap、drift detection 或 enforced activation。兩種模式都保留 Explicit Skill Lock：使用者只要在當次請求指定 SKILL，Profile support 就必須讓位，任何新增支援都要先取得 scoped consent。
