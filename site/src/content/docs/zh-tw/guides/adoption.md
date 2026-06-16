---
title: 客製化指南
description: 依照自己的 Agent skill catalog 調整 Workflow Skill Router。
---

## 從 starter 開始

把 `starter/workflow-skill-router/` 複製到你的 Agent skill 目錄。Starter 會提供輸出格式、route 結構，以及需要填寫的 reference files。

Workflow Skill Router 處理的是 Skill 選擇失控，不是授權問題。請保留既有的 scope contracts、runtime permissions、approval policies 與 tool access controls。

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

## 負責任地分享範例

分享 router 範例時，請使用虛構的公司情境。不要放入：

- 真實 repo 路徑
- 內部專案名稱
- 客戶名稱
- hostnames、tokens 和 secrets
- 部署分支名稱
- 受監管資料細節

可改用 `Acme Corp`、`Customer Portal`、`Internal Admin`、`Revenue Platform`、`Operations Dashboard` 這類佔位名稱。

## Source

- [查看 starter router](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [查看 adoption guide source](https://github.com/eric861129/Workflow-skill-router/blob/main/docs/adoption-guide.md)
- [查看 prompts](https://github.com/eric861129/Workflow-skill-router/tree/main/prompts)
