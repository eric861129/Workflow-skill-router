---
title: 從 V1 遷移至 V2
description: 以可回復的方式，從靜態 template router 移轉到 V2 Plugin 或純 SKILL contract。
---

## 主要差異

| V1 | V2 |
| --- | --- |
| 靜態 skill tree 與 route template | Runtime Capability Discovery 與 typed routing contract |
| 整個需求只使用一條 route | Single、Phased、Managed Goal envelopes |
| 寬鬆的輔助技能清單 | 最小化選擇與 Explicit Skill Lock |
| 以 validator 為主要證明 | Contract、runtime trace、Behavior、Outcome 證據分類 |
| 本機有檔案就視為可用 | Host exposure、auth、policy、freshness、risk 分別判斷 |

## 1. 盤點 V1 自訂規則

記錄 routes、衝突規則、使用者明確指定技能的處理方式，以及內部 capability 名稱。不要把公開 V1 Template Catalog 原封不動搬到 V2，只保留真實反映環境的規則。

## 2. 選擇安裝模式

環境支援時使用 [Plugin + MCP](/Workflow-skill-router/zh-tw/guides/install-plugin/)；Host 無法載入 Plugin 時使用[純 SKILL](/Workflow-skill-router/zh-tw/guides/install-skill/)。在新任務驗證 V2 routing 前，保留原本的 V1 安裝。

## 3. 轉換 policies

把 V1 Skill Tree 偏好轉成 Personal Routing Profile，不要壓平成一段全域 prompt。每個 workflow matcher 轉成一條 rule；每個 stage 轉成一個 `skill_tree` Phase，包含單一 Primary、最多三個 immediate support SKILL，以及 exit gate ID。

```powershell
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\migrated-v1-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\migrated-v1-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "代表性的 V1 任務" --work-mode phased
```

Personal Routing Profile commands 隨 `v2.0.0-beta.2` 提供；contributor checkout 請使用下方較長的 repository-relative runtime 路徑。

專案政策使用 `.codex/workflow-skill-router.json` 與 `scope: workspace`；跨專案個人偏好使用 `scope: personal`。Workspace 以整棵 route 取代 personal，不 deep merge。Runtime Capability Discovery 仍會把所選 SKILL 標成 `intended-unverified`，直到 activation 得到證明。

- 小型 route 轉成 `single`。
- 多階段 route 轉成 `phased`，每個 phase 都定義 verification gate。
- 可恢復且有相依性的工作轉成 `managed-goal` Work Items。
- 把「只使用 X」與「使用所有指定 SKILL」映射成 Explicit Skill Lock。
- 以 Runtime Capability Discovery 證據取代推測的 availability。

## 4. 並行驗證

執行具代表性的小型、分階段、explicit-lock 與 Goal 情境。比較預計使用的 SKILL、被拒絕的輔助技能、`capability-unavailable` 結果與最終使用揭露。公開 Flight Recorder 是預期的證據形狀，不是 production Host 證明。

## 5. 安全回復

若 V2 阻擋必要工作，停用 V2 Plugin，或把獨立 V2 SKILL 移出 active Skills 目錄，再恢復已知可用的 V1 設定。不可變的 [`v1.3.1` tag](https://github.com/eric861129/Workflow-skill-router/tree/v1.3.1) 與 GitHub Release 會保留 V1 原始碼與 packages。

只有在 removal manifest 完成審查並通過人工清理 gate 後，V1 檔案才會離開 V2 主分支。Git history 不是遷移方案；不可變 tag 才是 recovery source。
