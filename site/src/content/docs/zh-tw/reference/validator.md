---
title: 驗證工具鏈
description: 發布前驗證 V2 SKILL、公開面、生成契約、release packages 與 tests。
---

Workflow Skill Router 內建 local-first validation toolchain。Deterministic CI 不需要 Codex credentials，也不會消耗 live-model quota。

## 1. 驗證 router 結構

```bash
python scripts/validate-router.py starter/v2/workflow-skill-router
```

預期輸出：

```text
OK: workflow-skill-router passed validation
```

這會檢查 V2 frontmatter、routing／Goal／evaluation references、routing envelopes、Explicit Skill Lock、runtime capability 用語與誠實的 Skill-only fallback 標籤。

## 2. 檢查 public readiness

```bash
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
```

預期輸出：

```text
OK: public-readiness audit passed
```

這些檢查會強制 V2 public tree、governance files、Plugin/MCP 與 SKILL-only entrypoints、英文／繁中 route parity、local links、UTF-8 safety，以及已審查的 V1 removal boundary。

## 3. 驗證生成契約

```bash
python scripts/build-v2-demo-data.py --check
node scripts/build-mcp-reference-data.mjs --check
```

第一個命令證明 interactive Demo 來自 Router Core inputs；第二個命令證明公開 MCP reference 與十個真實 tool contracts、readiness matrix 一致。

## 4. 評估 routing quality

```bash
python scripts/run-v2-benchmark.py \
  --suite full \
  --evidence-class reference-driver \
  --adapter-executable python \
  --adapter-arg evaluation/v2/reference_driver.py \
  --repeats 3 \
  --output-dir dist/evaluation/v2/reference
```

Reference-driver 只證明 harness contract。Behavior evidence 必須另行授權 fresh-model run，並通過 36-attempt report 驗證；不存在時，公開狀態維持 `manual-required`。

## 5. 執行 unit tests

```bash
$env:PYTHONPATH = "packages/router-core/src"
python -m unittest discover -s packages/router-core/tests -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
```

測試涵蓋 Router Core、Plugin contracts、evaluation isolation、release reproducibility、installation smoke、public governance 與 documentation policy。

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

## Public URL / HTTPS smoke test

公開站台刻意使用 project path：`https://huangchiyu.com/Workflow-skill-router/`。除非專案未來搬到專屬 custom domain，否則不要在這個 repo 加 `CNAME`。

在這種設定下，GitHub Pages API 仍可能顯示 `cname=null` 或 `https_enforced=false`。公開 gate 以訪客實際行為為準：

```bash
curl -fsS --head https://huangchiyu.com/Workflow-skill-router/
curl -fsS -I -L http://huangchiyu.com/Workflow-skill-router/
```

預期：HTTPS 回 `200`，HTTP 最終導到 HTTPS project path。

## Source

- [在 GitHub 開啟 `scripts/validate-router.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [在 GitHub 開啟 `scripts/audit-public-readiness.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/audit-public-readiness.py)
- [在 GitHub 開啟 `scripts/run-v2-benchmark.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/run-v2-benchmark.py)
- [在 GitHub 開啟 `scripts/build-release-artifacts.py`](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/build-release-artifacts.py)
- [查看 V2 evaluation contracts](https://github.com/eric861129/Workflow-skill-router/tree/main/evaluation/v2)
