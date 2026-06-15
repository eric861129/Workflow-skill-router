---
title: 驗證工具鏈
description: 發布前驗證 router 結構、public readiness、skill inventory、routing quality 與 tests。
---

Workflow Skill Router 內建不依賴外部套件的 validation toolchain。發布 router repo、release 或公開 template package 前，請先執行這組檢查。

## 1. 驗證 router 結構

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
```

預期輸出：

```text
OK: workflow-skill-router passed validation
OK: template-skill-catalog passed validation
```

這會檢查 `SKILL.md`、必要 reference files、route `Primary:` markers、skill 數量上限、example README，以及 placeholder policy。

## 2. 檢查 public readiness

```bash
python scripts/audit-public-readiness.py .
```

預期輸出：

```text
OK: public-readiness audit passed
```

Audit 會檢查 community files、downloads、template catalog/manifest parity、site entrypoints、stale examples、亂碼、replacement characters，以及隱藏的 edit-link UI text。

舊的 validator flag 仍可使用：

```bash
python scripts/validate-router.py --public-readiness .
```

## 3. 掃描 skill catalog

```bash
python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md \
  --warnings /tmp/skill-warnings.md \
  --suggest-tree /tmp/suggested-skill-tree.md
```

正式 release gate 可加上 `--fail-on-private` 與 `--fail-on-duplicates`。Scanner 會輸出 machine-readable index、Markdown summary、warnings report 與 suggested skill tree。

## 4. 評估 routing quality

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations
```

若 primary mismatch 或 expected supporting skill 缺失也要讓 CI 失敗，請加上 `--strict`。

## 5. 執行 unit tests

```bash
python -m unittest discover -s tests
```

測試使用 Python standard-library `unittest`，涵蓋 evaluator 與 scanner。

## Lighthouse / Accessibility audit

公開發布前，可用這個命令檢查產生後的 Starlight 站台分數：

```bash
cd site
npm run audit:lighthouse
```

預期輸出：

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

這個 audit 會 build 站台、在本機 serve `site/dist`、對英文與繁中主要頁面跑 Lighthouse，並將 JSON/HTML 報告輸出到 `site/lighthouse-reports/`。

## Source

- [在 GitHub 開啟 `scripts/validate-router.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [在 GitHub 開啟 `scripts/audit-public-readiness.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/audit-public-readiness.py)
- [在 GitHub 開啟 `scripts/scan-skills.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/scan-skills.py)
- [在 GitHub 開啟 `scripts/evaluate-routing.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/evaluate-routing.py)
- [查看 evaluation examples](https://github.com/eric861129/Workflow-skill-router/tree/main/evaluation)
