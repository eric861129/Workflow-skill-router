---
title: Workflow Skill Router
description: 給多技能 AI Agent 使用的實戰 routing pattern。
template: splash
hero:
  title: 先路由，再開工
  tagline: Workflow Skill Router 會在複雜任務開始前，幫多技能 Agent 選出一個主要 skill，加上最多三個支援 skill。
  image:
    alt: 顯示 routing layer 如何選出聚焦 AI Agent skill 組合的圖
    file: ../../../assets/routing-pattern.svg
  actions:
    - text: 30 秒開始
      link: /Workflow-skill-router/zh-tw/guides/quickstart/
      icon: right-arrow
    - text: 下載套件
      link: /Workflow-skill-router/zh-tw/guides/downloads/
      icon: download
    - text: GitHub Repo
      link: https://github.com/eric861129/Workflow-skill-router
      icon: external
      variant: minimal
---

## 為什麼需要它

AI coding agent 可以同時擁有很多 skills、connectors 和 workflow。真正困難的地方，通常不是「Agent 會不會做」，而是「這次任務到底該啟用哪些能力」。

<div class="signal-grid">
  <div class="signal-card">
    <strong>Before</strong>
    一個前端 bug 同時觸發 UI、browser、Playwright、QA、design-system、docs、GitHub 和部署技能。
  </div>
  <div class="signal-card">
    <strong>After</strong>
    Agent 只選 frontend debugging、browser inspection 和 root-cause analysis。
  </div>
  <div class="signal-card">
    <strong>Result</strong>
    上下文更乾淨、意圖更明確，而且使用者可以在開工前修正路由。
  </div>
</div>

## Routing model

<div class="route-strip">
  <div class="route-step"><code>任務性質</code> 判斷這是 API、前端、文件、CI、connector、release 還是設計工作。</div>
  <div class="route-step"><code>工作階段</code> 區分規劃、實作、除錯、review、驗證與發布。</div>
  <div class="route-step"><code>技術領域</code> 選出一個 primary skill，加上最多三個 supporting skills。</div>
</div>

```text
Route: Frontend / Debugging > Browser reproduction > Customer portal
Use SKILL: frontend-debugging, browser, systematic-debugging
Reason: frontend-debugging handles rendered UI failures; browser reproduces the issue; systematic-debugging keeps the investigation causal.
```

## 你會得到什麼

- Codex-ready 的 starter skill。
- 可下載的空白與範本 skill package。
- 常見工程與公司平台情境的範例 routers。
- 可複製參考的 sample `SKILL.md`。
- 常見 workflow 的實戰 recipes。
- 不依賴外部套件的 validator。
- 依照自己的 skill catalog 客製 router 的指南。
