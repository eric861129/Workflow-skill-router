---
title: 下載
description: 下載空白 router skill，或先參考一套範例再設計自己的 router。
---

## 下載套件

大多數人先下載 **Blank Router** 就好。它提供乾淨的 router 結構，讓你填入自己的 skills、命名習慣、觸發條件、排除條件與 routing rules。**Reference Template** 是拿來理解結構與寫法的範例，不是要照抄成自己的最終 catalog。

<div class="wsr-download-picker" aria-label="下載套件比較">
  <article class="wsr-download-card wsr-download-card-featured">
    <div>
      <span class="wsr-download-kicker">主要下載</span>
      <h3>Blank Router</h3>
      <p>從乾淨的 router 開始。下載後放進 Codex skills，再填入自己的 skill tree、觸發詞、排除條件與 routing rules。</p>
    </div>
    <dl class="wsr-download-specs">
      <div>
        <dt>最適合</dt>
        <dd>想依照自己的開發習慣建立一套 router</dd>
      </div>
      <div>
        <dt>包含</dt>
        <dd><code>workflow-skill-router/</code> starter、routing rules、OpenAI agent metadata</dd>
      </div>
      <div>
        <dt>不包含</dt>
        <dd>Template catalog 與 sample skill folders</dd>
      </div>
    </dl>
    <a class="wsr-download-button" href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip">下載 Blank Router</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">參考範本</span>
      <h3>Reference Template</h3>
      <p>用一套 public-safe 範例理解 route、primary skill 與 supporting skills 如何組織。它適合學習與改造，不是最終成品。</p>
    </div>
    <dl class="wsr-download-specs">
      <div>
        <dt>最適合</dt>
        <dd>想先看完整寫法，再回去設計自己的 router</dd>
      </div>
      <div>
        <dt>包含</dt>
        <dd>Router、manifest、sample skills、root README</dd>
      </div>
      <div>
        <dt>不包含</dt>
        <dd>Private skills、sensitive lines、非必要 per-skill README files</dd>
      </div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip">下載 Reference Template</a>
  </article>
</div>

<div class="wsr-download-support">
  <a href="/Workflow-skill-router/zh-tw/examples/template-skill-catalog/">瀏覽對應的範本 Skill Catalog</a>
  <a href="https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md">查看範本 manifest</a>
  <a href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip">下載 Full source archive</a>
</div>

只有在需要 per-skill README、source context，或想 audit 範本來源時，才下載 **Full source archive**。

## 內容包含什麼

空白版包含：

```text
workflow-skill-router/
  SKILL.md
  agents/openai.yaml
  references/skill-tree.md
  references/routing-rules.md
```

Reference Template 包含：

```text
workflow-skill-router-template/
  README.md
  MANIFEST.md
  skills/
    workflow-skill-router/
    .system/
    <public-safe skill folders>
```

Reference Template 保留可安裝的 `skills/` tree，但移除非必要的 per-skill README。根目錄 README 與 manifest 仍會保留。

Reference Template 是公開安全版：從真實 `.codex/skills` 產生，排除組織專用 SKILL，並移除其他公開 skill 內的敏感行。這份範本會搭配 [範本 Skill Catalog](/Workflow-skill-router/zh-tw/examples/template-skill-catalog/) 使用，把下載包內的 SKILL 整理成可理解的 routes，方便你回頭設計自己的 router。

## Reference Template 包含的 SKILL

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

Reference Template 刻意不列出被排除的 private skill folder 名稱。你可以把這份清單當成 public-safe 的參考 catalog，再依照自己的 Agent 環境增減 SKILL。

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
- [下載 Reference Template](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip)
- [下載 Full source archive](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [查看 starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
