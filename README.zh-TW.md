# Workflow Skill Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Validation](https://img.shields.io/badge/validator-python%20scripts%2Fvalidate--router.py-brightgreen.svg)](scripts/validate-router.py)
[![Languages](https://img.shields.io/badge/docs-English%20%7C%20Traditional%20Chinese-informational.svg)](README.en.md)

> 一個實用的 AI Agent skill routing pattern，幫助 Agent 在複雜工作開始前，選出最小但足夠的 SKILL 組合。

**Not another prompt collection. A routing layer for multi-skill AI agents.**

這不是把 prompt 堆在一起的資料夾，而是讓 Agent 在工作前先選對技能組合的 routing layer。

現代 AI coding agent 可能同時擁有數十個 skills、tools、connectors 與 workflows。真正困難的不再是「Agent 能不能做這件事」，而是：

```text
這個任務應該啟用哪些 skills？
哪些 skills 只是相關，但不應該被載入？
規劃、實作、除錯、驗證，需要使用同一組 skills 嗎？
```

Workflow Skill Router 會把一串扁平的 skill list 變成一個決策入口：

```text
任務性質
  -> 工作階段
    -> 技術領域
      -> 1 個 Primary SKILL + 最多 3 個 Supporting SKILL
```

它不是 super skill。它是一個小而清楚的前門，告訴 Agent 下一步該載入什麼。

![Workflow Skill Router before and after demo](docs/assets/demo-routing-before-after.svg)

## 前後對比

沒有 routing 時，一個前端 bug 很容易觸發所有看起來相關的 skills：

```text
frontend, ui, browser, playwright, qa, design-system, github, docs, deployment
```

有 routing 後，Agent 會先選出小而聚焦的工作組合：

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: vue-expert, systematic-debugging, playwright
Reason: vue-expert 處理 component 行為；systematic-debugging 維持因果式排查；playwright 固化回歸驗證。
```

## 30 秒快速開始

英文站台：`https://huangchiyu.com/Workflow-skill-router/`
繁中站台：`https://huangchiyu.com/Workflow-skill-router/zh-tw/`

1. 將 starter 複製到你的 Agent skill 目錄：

   ```text
   starter/workflow-skill-router/
   ```

2. 請 Agent 盤點可用的 skills，並補齊：

   ```text
   workflow-skill-router/
     SKILL.md
     references/
       skill-tree.md
       routing-rules.md
   ```

3. 驗證 router：

   ```bash
   python scripts/validate-router.py starter/workflow-skill-router
   ```

預期結果：

```text
OK: workflow-skill-router passed validation
```

如果你準備發布自己的 router package 或公開 examples，請再跑完整 repo audit：

```bash
python scripts/audit-public-readiness.py .
```

預期結果：

```text
OK: public-readiness audit passed
```

公開站台前，請跑正式 Lighthouse / accessibility 品質 gate：

```bash
cd site
npm run audit:lighthouse
```

這會 build Starlight 站台，對英文與繁中主要頁面跑 Lighthouse，並把本機報告輸出到 `site/lighthouse-reports/`。

## 下載 SKILL 套件

- [空白 SKILL 套件](downloads/workflow-skill-router-blank.zip)：可直接安裝的 `workflow-skill-router/` starter，適合想建立自己 skill tree 的使用者。
- [範本 SKILL 套件](downloads/workflow-skill-router-template.zip)：從維護者實際本機 Codex skills catalog 匿名化整理而成，包含 sanitized `workflow-skill-router` 與實務上會用到的 public skills。
- [Template Skill Catalog](examples/template-skill-catalog)：與範本套件對齊的 route catalog。
- [Template manifest](downloads/workflow-skill-router-template-manifest.md)：列出包含的 skill folders、排除的 private skill 數量與 sanitization summary。

在本機重新產生兩個 zip：

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

Package builder 不會偷偷使用預設本機 skills 目錄。除非你明確傳入 `--allow-no-private-filters` 並已自行檢查來源目錄，否則至少需要一個 private filter。

範本套件來自真實 `.codex/skills` 目錄，但已排除組織專屬 skills，並移除 public skills 中可能含有敏感內容的行。

## 實用 Routing 範例

### API 合約同步

```text
使用者：新增 customer settings endpoint，更新 OpenAPI，並讓前端 client 跟上新合約。

Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, qa-test-planner
Reason: api-designer 穩定 endpoint 設計；openapi-contract-generation-skill 管理 schema diff 與 contract generation；openapi-to-typescript 更新 client types；qa-test-planner 定義合約測試覆蓋。
```

### 資料庫 Migration 與效能風險

```text
使用者：替 account changes 新增 audit tables，並確認 admin query 不會變慢。

Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer 負責 migration shape；sql-pro 檢查 SQL 正確性；database-optimizer 檢查 query plans；qa-test-planner 定義回歸覆蓋。
```

### 只在瀏覽器出現的前端 Bug

```text
使用者：customer portal 表單只有在 browser refresh 後會失敗，請重現並補上 regression check。

Route: Frontend / Vue / UI > Browser regression
Use SKILL: vue-expert, systematic-debugging, playwright
Reason: vue-expert 處理 component 行為；systematic-debugging 維持因果式排查；playwright 固化回歸驗證。
```

### PR Review 與 CI 修復

```text
使用者：Review 這個 auth PR，處理 comments，並修好 failing checks。

Route: Review / CI readiness > Security-sensitive change
Use SKILL: receiving-code-review, systematic-debugging, qa-test-planner, commit-work
Reason: receiving-code-review 處理 review feedback；systematic-debugging 隔離 failing checks；qa-test-planner 定義驗證範圍；commit-work 保持最後提交乾淨。
```

### 本機開發環境

```text
使用者：建立 Docker Compose setup，包含 PostgreSQL、Redis 與 MailDev，讓本機開發可以重複啟動。

Route: DevOps / Local development > Repeatable service stack
Use SKILL: docker-compose-local-dev-skill, devops-engineer, systematic-debugging
Reason: docker-compose-local-dev-skill 負責本機服務體驗；devops-engineer 檢查基礎設施取捨；systematic-debugging 協助處理啟動順序與 health checks。
```

## Repo 內容

- `starter/workflow-skill-router/`：Codex-ready starter skill，保留 agent-agnostic routing contract。
- `examples/template-skill-catalog/`：單一公開範例 catalog，對齊 template download package。
- `sample-skills/`：可複製參考的 public `SKILL.md` 範例，搭配 template catalog 使用。
- `downloads/`：產生好的空白與範本 SKILL zip 套件。
- `recipes/`：API 合約同步、前端除錯、PR/CI、文件、connector-heavy workflow 等短指南。
- `scripts/validate-router.py`：無外部依賴的 validator，除了檢查 router 結構，也提供 public-readiness audit，確認 community files、downloads、template catalog/manifest parity、site assets 與舊 examples。
- `scripts/audit-public-readiness.py`：公開前專用的 release gate，使用與 `validate-router.py --public-readiness` 相同的檢查邏輯。
- `scripts/package-downloads.py`：無外部依賴的 SKILL zip packaging 工具。
- `site/`：部署到 GitHub Pages 的 Astro Starlight 站台。
- `site/scripts/lighthouse-audit.mjs`：公開站台的 Lighthouse 與 accessibility 正式分數 gate。
- `prompts/`：建立或維護個人 router 時可直接複製的 prompts。
- `docs/`：概念文件、自訂指南與驗證 checklist。

## 範例 Routers

| Example | 適用情境 |
| --- | --- |
| `examples/template-skill-catalog` | 將可下載 template package 整理成實用且 public-safe 的 route categories |

## 常見問題

### 這和一般 system prompt 差在哪？

System prompt 定義 Agent 的整體行為；Workflow Skill Router 先判斷這個任務該載入哪些 skill instructions。它站在執行前：分類任務、選 1 個 Primary SKILL、最多 3 個 Supporting SKILL，並用一句話說明原因。

### 為什麼限制 1-4 個 skills？

限制讓 context 保持集中。一個 Primary SKILL 負責主軸；Supporting SKILL 只補足領域、驗證或工具。若任務真的需要超過 4 個 skills，應拆成多個階段，各階段分別 routing。

### 可以用在 Claude / Cursor / Gemini 嗎？

可以。這個 pattern 是 agent-agnostic。starter 對 Codex 友善，但核心契約只是文字：skill inventory、routing rules、sample routes 與 validator。只要 Agent 能讀專案規則或自訂 instructions，就能改成自己的版本。

## 延伸閱讀

- [English guide](README.en.md)
- [Website](https://huangchiyu.com/Workflow-skill-router/)
- [繁中站台](https://huangchiyu.com/Workflow-skill-router/zh-tw/)
- [自訂指南](docs/adoption-guide.zh-TW.md)
- [系統理論](docs/system-theory.zh-TW.md)
- [驗證 checklist](docs/validation-checklist.zh-TW.md)

## 授權

MIT。請見 [LICENSE](LICENSE)。
