# 客製化指南

Workflow Skill Router 是一個 starter pattern。你可以依照自己的 Agent skill catalog，整理出適合目前環境的 routing rules。

## Step 1：複製 starter

把 `starter/workflow-skill-router/` 複製到你的 Agent skill 目錄。

## Step 2：盤點你的 skills

先依來源分組：

- local custom skills
- connector 或 plugin skills
- system skills
- meta workflow skills
- file-format skills

特別標出容易過度觸發的 skills，例如太寬泛的 design、writing、planning、meta workflow skills。

## Step 3：依工作階段建立 routes

不要只寫一個很寬的分類，例如 `frontend skills`。改用工作階段拆開：

- new app or page
- browser debugging
- visual design
- design system work
- scripted regression testing

每條 route 應該選一個 Primary skill，加上最多三個 Supporting skills。

## Step 4：補上衝突規則

衝突規則是 router 最有價值的地方。常見重疊包含：

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## Step 5：負責任地分享範例

分享 router 範例時，請使用虛構的公司情境。不要放入：

- 真實 repository 路徑
- 內部專案名稱
- 客戶名稱
- 部署 branch 名稱
- secrets、domains、tokens、hostnames
- 受管制或敏感資料描述

可使用 `Acme Corp`、`Customer Portal`、`Internal Admin`、`Revenue Platform`、`Operations Dashboard` 這類 placeholder 名稱。

## Step 6：驗證

執行：

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

發布或分享 example router 前，也應該逐一驗證。
