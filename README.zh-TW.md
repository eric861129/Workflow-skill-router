# Workflow Skill Router

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Validation](https://img.shields.io/badge/validator-python%20scripts%2Fvalidate--router.py-brightgreen.svg)](scripts/validate-router.py)
[![Languages](https://img.shields.io/badge/docs-English%20%7C%20Traditional%20Chinese-informational.svg)](README.en.md)

> 協助多技能 AI Agent 在開始複雜任務前，先選出最小且足夠的 SKILL 組合。

當 AI coding agent 擁有越來越多 SKILL、工具、connector、workflow 時，真正困難的常常不是能力不足，而是選擇品質：

```text
這次任務到底該啟用哪些 SKILL？
哪些只是相關，但不該載入？
需求、設計、實作、除錯、驗證，應該用同一組 SKILL 嗎？
```

Workflow Skill Router 把平面技能清單整理成一層決策模型：

```text
任務性質
  -> 工作階段
    -> 技術領域
      -> 1 個 Primary SKILL + 最多 3 個 Supporting SKILL
```

它不是 super skill，而是讓 Agent 先走對入口的小型路由層。

## Before And After

沒有 routing 時，一個前端錯誤可能觸發所有看起來相關的能力：

```text
frontend, ui, browser, playwright, qa, design-system, github, docs, deployment
```

有 routing 後，Agent 只選必要組合：

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: frontend-debugging, browser, systematic-debugging
Reason: frontend-debugging handles rendered UI failures; browser reproduces the issue; systematic-debugging keeps the investigation causal.
```

## 30 秒快速開始

網站：`https://huangchiyu.com/Workflow-skill-router/`
繁中站台：`https://huangchiyu.com/Workflow-skill-router/zh-tw/`

1. 複製 starter 到你的 Agent skill 目錄：

   ```text
   starter/workflow-skill-router/
   ```

2. 讓 Agent 盤點目前可用 SKILL，並填入：

   ```text
   workflow-skill-router/
     SKILL.md
     references/
       skill-tree.md
       routing-rules.md
   ```

3. 執行驗證：

   ```bash
   python scripts/validate-router.py starter/workflow-skill-router
   ```

預期結果：

```text
OK: workflow-skill-router passed validation
```

## 下載 SKILL 套件

- [空白 SKILL 套件](downloads/workflow-skill-router-blank.zip)：可直接安裝的 `workflow-skill-router/` starter，適合你要自己填 skill tree。
- [範本 SKILL 套件](downloads/workflow-skill-router-template.zip)：公開安全版的實戰 Codex skills pack，包含匿名化後的 `workflow-skill-router`，以及實際使用中可公開的 SKILL。
- [範本 manifest](downloads/workflow-skill-router-template-manifest.md)：列出包含的 skill folders、排除的 private skill 數量與匿名化摘要。

本機重新產生兩個 zip：

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

打包工具不會使用隱含的本機 skills 目錄。除非你明確加上 `--allow-no-private-filters` 並已自行檢查來源目錄，否則至少要提供一個 private filter。

範本包是從真實本機 `.codex/skills` 產生的公開安全版，會排除 private organization-specific skills，並移除其他公開 skill 內的 private lines。

## 更實際的 Routing 範例

### API 合約與前端同步

```text
使用者：新增 customer settings endpoint，更新 OpenAPI，並讓前端 client 跟上。

Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, build-web-apps:frontend-testing-debugging
Reason: api-designer 穩定 endpoint 設計；openapi-contract-generation-skill 處理 schema diff 與 contract generation；openapi-to-typescript 更新 client types；frontend-testing-debugging 驗證畫面端使用情境。
```

### 資料庫 Migration 與效能風險

```text
使用者：新增帳號異動 audit tables，並確認 admin 查詢不會變慢。

Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer 負責 migration shape；sql-pro 檢查 SQL 正確性；database-optimizer 檢查 query plan；qa-test-planner 補上回歸測試面。
```

### 只在瀏覽器發生的前端 Bug

```text
使用者：customer portal 表單在 refresh 後才會壞，請重現並補 regression check。

Route: Frontend / Debugging > Browser reproduction
Use SKILL: build-web-apps:frontend-testing-debugging, browser:control-in-app-browser, playwright, systematic-debugging
Reason: frontend-testing-debugging 對應 UI 症狀到前端來源；browser 重現真實 runtime 行為；playwright 固化回歸測試；systematic-debugging 保持因果式排查。
```

### PR Review 與 CI 修復

```text
使用者：review 這個 auth PR，處理 comments，並修掉 failing checks。

Route: GitHub / Review and CI > Security-sensitive PR
Use SKILL: github:github, receiving-code-review, codex-security:security-diff-scan, github:gh-fix-ci
Reason: github:github 定位 PR 狀態；receiving-code-review 處理 review comments；security-diff-scan 檢查 auth 與資料外洩風險；gh-fix-ci 診斷 failing checks。
```

### 本機開發環境

```text
使用者：建立 Docker Compose，包含 PostgreSQL、Redis、MailDev，讓新成員可以一鍵啟動。

Route: DevOps / Local development > Repeatable service stack
Use SKILL: docker-compose-local-dev-skill, devops-engineer, systematic-debugging
Reason: docker-compose-local-dev-skill 負責本機服務設計；devops-engineer 檢查基礎設施取捨；systematic-debugging 處理啟動順序與 health check 問題。
```

## 這個 repo 包含什麼

- `starter/workflow-skill-router/`：Codex-ready starter，同時保留 agent-agnostic routing contract。
- `examples/`：範例 routers，從最小 generic agent 到真實工程 workflow。
- `sample-skills/`：可複製參考的公開 `SKILL.md` 範例，對應 common engineering routes。
- `downloads/`：已產生的空白與範本 SKILL zip 套件。
- `recipes/`：API 合約同步、前端除錯、PR/CI、文件圖表、connector-heavy workflow 的實用模式。
- `scripts/validate-router.py`：無外部相依的 validator，檢查結構、route 數量、Primary 標記與隱私字串。
- `scripts/package-downloads.py`：無外部相依的下載套件打包工具。
- `site/`：可部署到 GitHub Pages 的 Astro Starlight 網站。
- `prompts/`：建立與維護個人化 router 的 prompt。
- `docs/`：方法論、客製化指南與驗證清單。

## 範例 Router

| 範例 | 適合情境 |
| --- | --- |
| `examples/generic-agent` | 任何擁有小型 skill catalog 的 Agent |
| `examples/common-engineering-routing` | 使用實際 skill 名稱的常見工程 routing 情境 |
| `examples/enterprise-fullstack` | 後端、前端、文件、CI、release routing |
| `examples/frontend-debugging` | Browser、Playwright、UI debugging 的選擇 |
| `examples/github-ci-review` | GitHub PR review、CI failure、release readiness |
| `examples/company-platform-sanitized` | 匿名化公司平台 workflow，保留真實複雜度 |

## 更多文件

- [English guide](README.en.md)
- [網站](https://huangchiyu.com/Workflow-skill-router/)
- [繁中站台](https://huangchiyu.com/Workflow-skill-router/zh-tw/)
- [客製化指南](docs/adoption-guide.zh-TW.md)
- [系統論](docs/system-theory.zh-TW.md)
- [驗證清單](docs/validation-checklist.zh-TW.md)

## 授權

MIT。請見 [LICENSE](LICENSE)。
