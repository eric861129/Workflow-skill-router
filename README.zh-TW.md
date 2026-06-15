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

## 這個 repo 包含什麼

- `starter/workflow-skill-router/`：Codex-ready starter，同時保留 agent-agnostic routing contract。
- `examples/`：範例 routers，從最小 generic agent 到真實工程 workflow。
- `sample-skills/`：可複製參考的公開 `SKILL.md` 範例，對應 common engineering routes。
- `recipes/`：API 合約同步、前端除錯、PR/CI、文件圖表、connector-heavy workflow 的實用模式。
- `scripts/validate-router.py`：無外部相依的 validator，檢查結構、route 數量、Primary 標記與隱私字串。
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
