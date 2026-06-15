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

## Public-readiness audit

準備發布 router repo、release 或公開 template package 前，請執行：

```bash
python scripts/audit-public-readiness.py .
```

預期輸出：

```text
OK: public-readiness audit passed
```

Audit 會檢查：

- README、license、security policy、code of conduct、contributing guide、funding metadata、issue templates 與 PR template。
- starter router 與 template example validation。
- blank/template downloads 與 manifest files。
- template catalog routes 是否覆蓋 template manifest 列出的每個 skill，且沒有引用 manifest 以外的 skill。
- Starlight site entrypoints、robots file 與 social preview asset。
- 是否還殘留會和單一 Template Skill Catalog 敘事衝突的舊 examples。
- 亂碼、replacement characters，以及隱藏的 edit-link UI text。

舊的 validator flag 仍保留給既有流程使用：

```bash
python scripts/validate-router.py --public-readiness .
```

## Lighthouse / Accessibility audit

公開發布前，請用這個命令檢查產生後的 Starlight 站台分數：

```bash
cd site
npm run audit:lighthouse
```

預期輸出：

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

這個 audit 會 build 站台、在本機 serve `site/dist`、對英文與繁中主要頁面跑 Lighthouse，並將 JSON/HTML 報告輸出到 `site/lighthouse-reports/`。

## Self-test

```bash
python scripts/validate-router.py --self-test
```

預期輸出：

```text
OK: validator self-test passed
```

## Source

- [在 GitHub 開啟 `scripts/audit-public-readiness.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/audit-public-readiness.py)
- [在 GitHub 開啟 `scripts/validate-router.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [在 GitHub 開啟 `site/scripts/lighthouse-audit.mjs`](https://github.com/eric861129/Workflow-skill-router/blob/main/site/scripts/lighthouse-audit.mjs)
- [查看指令使用的 starter router](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [查看 example routers](https://github.com/eric861129/Workflow-skill-router/tree/main/examples)
