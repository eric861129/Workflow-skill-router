---
title: Workflow Skill Router
description: A practical routing pattern for multi-skill AI agents.
template: splash
hero:
  title: Route before your AI agent works
  tagline: Workflow Skill Router helps multi-skill agents choose one primary skill plus up to three supporting skills before complex work starts.
  image:
    alt: Diagram showing a routing layer selecting a focused AI agent skill set
    file: ../../assets/routing-pattern.svg
  actions:
    - text: Start in 30 seconds
      link: /Workflow-skill-router/guides/quickstart/
      icon: right-arrow
    - text: Download packages
      link: /Workflow-skill-router/guides/downloads/
      icon: download
    - text: View on GitHub
      link: https://github.com/eric861129/Workflow-skill-router
      icon: external
      variant: minimal
---

## Why this exists

AI coding agents can have dozens of skills, connectors, and workflows. Without a routing layer, agents often treat every related skill as required.

<div class="signal-grid">
  <div class="signal-card">
    <strong>Before</strong>
    A frontend bug triggers UI, browser, Playwright, QA, design-system, docs, GitHub, and deployment skills at once.
  </div>
  <div class="signal-card">
    <strong>After</strong>
    The agent selects frontend debugging, browser inspection, and systematic root-cause analysis.
  </div>
  <div class="signal-card">
    <strong>Result</strong>
    Less context noise, clearer intent, and a route the user can correct before work begins.
  </div>
</div>

## The routing model

<div class="route-strip">
  <div class="route-step"><code>Task nature</code> decides whether this is API, frontend, docs, CI, connector, release, or design work.</div>
  <div class="route-step"><code>Work stage</code> separates planning, implementation, debugging, review, verification, and release.</div>
  <div class="route-step"><code>Technical domain</code> chooses one primary skill plus up to three supporting skills.</div>
</div>

```text
Route: Frontend / Debugging > Browser reproduction > Single-page app
Use SKILL: frontend-debugging, browser, systematic-debugging
Reason: frontend-debugging handles rendered UI failures; browser reproduces the issue; systematic-debugging keeps the investigation causal.
```

## What you get

- A Codex-ready starter skill.
- Downloadable blank and template skill packages.
- Common engineering and company-focused example routers.
- Copyable sample `SKILL.md` files.
- Practical recipes for common workflows.
- A dependency-free validator.
- A customization guide for adapting the router to your own skill catalog.

## Source shortcuts

- [Starter router source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
- [Example routers](https://github.com/eric861129/Workflow-skill-router/tree/main/examples)
- [Sample skills](https://github.com/eric861129/Workflow-skill-router/tree/main/sample-skills)
- [Download packages](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [Full source map](/Workflow-skill-router/reference/source-map/)
