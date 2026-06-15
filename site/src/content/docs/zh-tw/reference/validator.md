---
title: Validator CLI
description: 在發布或分享 router package 前，先驗證結構、公開入口與隱私風險。
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

Router package validation：

- `SKILL.md` 存在。
- YAML frontmatter 只包含 `name` 與 `description`。
- `references/skill-tree.md` 存在。
- `references/routing-rules.md` 存在。
- route lines 包含 `Primary:`。
- 每條 route 最多選擇四個 skills。
- examples 包含 `README.md`。
- starter placeholder skills 有清楚標註。
- router files 不包含明顯 private identifiers。

## Public-readiness audit

準備發布 router repo、release 或公開 template package 前，請執行：

```bash
python scripts/validate-router.py --public-readiness .
```

預期輸出：

```text
OK: public-readiness audit passed
```

Audit 會檢查：

- README、license、security policy、code of conduct、contributing guide、funding metadata、issue templates 與 PR template。
- starter router 與 template example validation。
- blank/template downloads 與 manifest files。
- Starlight site entrypoints、robots file 與 social preview asset。
- 是否還殘留會和單一 Template Skill Catalog 敘事衝突的舊 examples。
- 明顯 private identifiers、學校或內部名稱、亂碼、replacement characters，以及隱藏的 edit-link UI text。

## Self-test

```bash
python scripts/validate-router.py --self-test
```

預期輸出：

```text
OK: validator self-test passed
```

## Source

- [在 GitHub 開啟 `scripts/validate-router.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [查看指令使用的 starter router](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [查看 example routers](https://github.com/eric861129/Workflow-skill-router/tree/main/examples)
