---
title: 下載
description: 下載空白 router skill 或實戰範本 skill package。
---

## 下載套件

如果你想先安裝 router，再依照自己的 Agent skill catalog 從零開始填 skill tree，請下載空白版。

- [下載空白 SKILL](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip)

如果你想直接參考一組從真實本機 Codex skills catalog 產生的公開安全實戰範本，請下載範本包。

- [下載範本 SKILL 套件](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [瀏覽對應的範本 Skill Catalog](/Workflow-skill-router/zh-tw/examples/template-skill-catalog/)
- [查看範本 manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)

## 內容包含什麼

空白版包含：

```text
workflow-skill-router/
  SKILL.md
  agents/openai.yaml
  references/skill-tree.md
  references/routing-rules.md
```

範本包包含：

```text
workflow-skill-router-template/
  README.md
  MANIFEST.md
  skills/
    workflow-skill-router/
    .system/
    <public-safe skill folders>
```

範本包是公開安全版：從真實 `.codex/skills` 產生，排除組織專用 SKILL，並移除其他公開 skill 內的敏感行。現在這份範本包會搭配 [範本 Skill Catalog](/Workflow-skill-router/zh-tw/examples/template-skill-catalog/) 使用，直接把下載包內的 SKILL 整理成可理解、可複製的 routes。

## 範本包包含的 SKILL

### Router 與 Codex 系統工具

這一組是安裝、建立、維護 SKILL 時最核心的工具，也包含本專案的 router 本體。

- `.system/imagegen`
- `.system/openai-docs`
- `.system/plugin-creator`
- `.system/skill-creator`
- `.system/skill-installer`
- `workflow-skill-router`

### 需求、規劃、執行與交接

這一組用在需求釐清、任務拆解、計畫執行、收尾、handoff，以及讓 Agent 維持穩定工程節奏。

- `requirements-clarity`
- `executing-plans`
- `session-handoff`
- `finishing-a-development-branch`
- `commit-work`
- `receiving-code-review`
- `karpathy-guidelines`
- `writing-clearly-and-concisely`

### 架構、API、後端與資料庫

這一組用在系統設計、API 合約、OpenAPI/TypeScript 同步、C#/.NET、資料庫 schema、SQL 與效能調校。

- `architecture-designer`
- `c4-architecture`
- `cloud-architect`
- `api-designer`
- `api-guidelines-skill`
- `openapi-contract-generation-skill`
- `openapi-to-typescript`
- `csharp-developer`
- `dotnet-core-expert`
- `database-schema-designer`
- `database-optimizer`
- `sql-pro`

### 前端、Vue、UI 與設計系統

這一組用在前端實作、Vue Composition API、UI polish、設計系統、Storybook、Tailwind token、截圖轉程式碼與視覺重設計。

- `frontend-design`
- `vue-expert`
- `vue-composition-patterns-skill`
- `design-system`
- `design-system-starter`
- `storybook-design-system-skill`
- `tailwind-design-token-skill`
- `ui-styling`
- `ui-ux-pro-max`
- `gpt-tasteskill`
- `minimalist-skill`
- `soft-skill`
- `taste-skill`
- `redesign-skill`
- `image-to-code-skill`
- `imagegen-frontend-web`
- `imagegen-frontend-mobile`

### DevOps、本機開發與依賴管理

這一組用在 Docker Compose、本機服務堆疊、CI/CD、雲端/部署思考與 dependency 更新。

- `devops-engineer`
- `docker-compose-local-dev-skill`
- `dependency-updater`

### 測試、除錯、瀏覽器與品質驗證

這一組用在系統性除錯、Playwright、QA test plan、回歸測試與實際瀏覽器驗證。

- `systematic-debugging`
- `playwright`
- `qa-test-planner`

### 文件、圖表、檔案與規格整理

這一組用在技術文件、使用者文件、Mermaid/C4 圖、PDF、規格反推、共同撰寫與檔案整理。

- `code-documenter`
- `doc-coauthoring`
- `mermaid-diagrams`
- `pdf`
- `spec-miner`
- `file-organizer`
- `agent-md-refactor`

### 產品、品牌、視覺與跨平台應用

這一組用在品牌語氣、banner、視覺設計、Flutter App，以及比較偏產品化或推廣面的工作。

- `brand`
- `banner-design`
- `design`
- `flutter-expert`

範本包刻意不列出被排除的 private skill folder 名稱。你可以把這份清單當成 public-safe 的參考 catalog，再依照自己的 Agent 環境增減 SKILL。

## 本機重新打包

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

打包工具不會使用隱含的本機 skills 目錄。除非你明確加上 `--allow-no-private-filters` 並已自行檢查來源目錄，否則至少要提供一個 private filter。

## Source

- [在 GitHub 開啟 `downloads/`](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [查看範本 Skill Catalog source](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [查看 package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [查看範本 manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)
- [查看 starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
