---
title: Validator CLI
description: 在發布或分享 router package 前先驗證結構與隱私風險。
---

Repo 內建不依賴外部套件的 validator：

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

預期輸出：

```text
OK: workflow-skill-router passed validation
```

## 檢查項目

- `SKILL.md` 存在。
- YAML frontmatter 只包含 `name` 和 `description`。
- `references/skill-tree.md` 存在。
- `references/routing-rules.md` 存在。
- route lines 包含 `Primary:`。
- 每條 route 最多選四個 skills。
- examples 包含 `README.md`。
- 公開範例不包含明顯 private identifiers。

## Self-test

```bash
python scripts/validate-router.py --self-test
```

預期輸出：

```text
OK: validator self-test passed
```
