---
title: Routing Contract
description: 每個 workflow skill router 都應該使用的穩定輸出格式。
---

## 複雜任務

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

## 簡單任務

```text
No extra routing needed: reason
```

## Route rules

- 最多選四個 skills。
- 必須剛好有一個 primary skill。
- supporting skills 只在負責不同工作時加入。
- 當 live external state 是事實來源時，優先使用 connector。
- 如果看起來需要超過四個 skills，代表任務應該拆成多個階段。

## Good route

```text
Route: GitHub / PR comments > Address feedback > Remote review
Use SKILL: github-review-comments, code-review, local-editing, test-runner
Reason: github-review-comments fetches unresolved feedback; code-review evaluates it; local-editing applies changes; test-runner verifies behavior.
```

## Noisy route

```text
Use SKILL: github, code-review, ci, devops, docs, browser, release, planning
```

這條 route 太寬，應該依照工作階段拆開。

## Source

- [在 GitHub 開啟 starter `SKILL.md`](https://github.com/eric861129/Workflow-skill-router/blob/main/starter/workflow-skill-router/SKILL.md)
- [查看 starter routing rules](https://github.com/eric861129/Workflow-skill-router/blob/main/starter/workflow-skill-router/references/routing-rules.md)
