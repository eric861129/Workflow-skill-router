# 採用指南

Workflow Skill Router 最適合採用「公開核心 + 私有 overlay」的方式。

## 建議模型

```text
public core
  -> 共用任務模型
  -> 輸出格式
  -> SKILL 數量限制
  -> connector 優先規則

private overlay
  -> 真實 repo 名稱
  -> 內部系統
  -> 部署規則
  -> 客戶資料政策
  -> 團隊 review gate
```

## Step 1：先使用公開核心

把 `starter/workflow-skill-router/` 複製到你的 Agent skill 目錄。Starter 應該描述 routing 方法，而不是塞滿公司內部細節。

## Step 2：盤點你的 SKILL

依來源分組：

- local custom skills
- connector 或 plugin skills
- system skills
- meta workflow skills
- file-format skills

另外標記容易過度觸發的 SKILL。這類通常是範圍很廣的設計、寫作、規劃、meta workflow 類 SKILL。

## Step 3：用工作階段建立路由

不要只寫「frontend skills」這種平面分類。要依工作階段拆開：

- 新頁面或新 App
- Browser debugging
- 視覺設計
- Design system
- Scripted regression testing

每條 route 應該只有一個 Primary SKILL，最多三個 Supporting SKILL。

## Step 4：加入衝突規則

衝突規則是 router 最有價值的地方。常見重疊包含：

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## Step 5：公開範例不要放私有細節

發布範例前，移除：

- 真實 repository 路徑
- 內部專案名稱
- 客戶名稱
- 部署 branch 名稱
- secrets、domains、tokens、hostnames
- 受管制或敏感資料描述

請使用公司情境 placeholder，例如 `Acme Corp`、`Customer Portal`、`Internal Admin`、`Revenue Platform`、`Operations Dashboard`。

## Step 6：驗證

執行：

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

發布前也要驗證每一個 example router。

