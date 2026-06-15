---
title: 導入指南
description: 用 public core 和 private overlay，讓 routing 同時可分享又能保留公司脈絡。
---

## 建議結構

公開 repo 保留通用 routing 規則，公司細節放在 private overlay。

```text
public core
  -> task model
  -> output contract
  -> skill count rules
  -> connector priority

private overlay
  -> repository names
  -> internal systems
  -> deployment rules
  -> customer data policies
```

## 盤點你的 skills

先依來源分組：

- local custom skills
- connector 或 plugin skills
- system skills
- meta workflow skills
- file-format skills

特別標出容易過度觸發的技能，例如太寬泛的 writing、design、planning、meta workflow skills。

## 寫清楚衝突規則

Router 最有價值的地方，是它能處理「看起來都相關，但其實不該一起啟用」的衝突。

常見衝突：

- connector skill vs local reasoning skill
- browser inspection vs scripted browser automation
- PR review connector vs code review reasoning
- file-format tool vs generic documentation skill
- broad meta workflow vs narrow implementation skill

## 匿名化公開範例

公開之前，移除：

- 真實 repo 路徑
- 內部專案名稱
- 客戶名稱
- hostnames、tokens 和 secrets
- 部署分支名稱
- 受監管資料細節

可改用 `Acme Corp`、`Customer Portal`、`Internal Admin`、`Revenue Platform`、`Operations Dashboard` 這類佔位名稱。
