---
title: Downloads
description: Download a blank router skill, or study a reference template before designing your own router.
---

## Download packages

Most readers should start with **Blank Router**. It gives you the router structure so you can add your own skills, naming conventions, triggers, exclusions, and routing rules. **Reference Template** is a working example to learn from, not a catalog you need to copy as-is.

<div class="wsr-download-picker" aria-label="Package comparison">
  <article class="wsr-download-card wsr-download-card-featured">
    <div>
      <span class="wsr-download-kicker">Primary download</span>
      <h3>Blank Router</h3>
      <p>Start from a clean router. Install it into Codex skills, then fill in your own skill tree, trigger words, exclusions, and routing rules.</p>
    </div>
    <dl class="wsr-download-specs">
      <div>
        <dt>Best for</dt>
        <dd>Building your own router around your real development habits</dd>
      </div>
      <div>
        <dt>Includes</dt>
        <dd><code>workflow-skill-router/</code> starter, routing rules, OpenAI agent metadata</dd>
      </div>
      <div>
        <dt>Excludes</dt>
        <dd>Template catalog and sample skill folders</dd>
      </div>
    </dl>
    <a class="wsr-download-button" href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-blank.zip" data-analytics-event="site_download_blank_router">Download Blank Router</a>
  </article>

  <article class="wsr-download-card">
    <div>
      <span class="wsr-download-kicker">Learning reference</span>
      <h3>Reference Template</h3>
      <p>Study a public-safe example catalog to see how routes, primary skills, and supporting skills are organized. Use it as a model, then design your own router.</p>
    </div>
    <dl class="wsr-download-specs">
      <div>
        <dt>Best for</dt>
        <dd>Learning the structure before adapting Blank Router</dd>
      </div>
      <div>
        <dt>Includes</dt>
        <dd>Router, manifest, sample skills, root README</dd>
      </div>
      <div>
        <dt>Excludes</dt>
        <dd>Private skills, sensitive lines, non-essential per-skill README files</dd>
      </div>
    </dl>
    <a class="wsr-download-button wsr-download-button-secondary" href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip" data-analytics-event="site_download_reference_template">Download Reference Template</a>
  </article>
</div>

<div class="wsr-download-support">
  <a href="/Workflow-skill-router/examples/template-skill-catalog/">Browse the matching Template Skill Catalog</a>
  <a href="https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md">View template manifest</a>
  <a href="https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip" data-analytics-event="site_download_full_source">Download Full source archive</a>
</div>

Download **Full source archive** only when you need per-skill README files, source context, or audit material behind the reference template.

## What is inside

The blank package contains:

```text
workflow-skill-router/
  SKILL.md
  agents/openai.yaml
  references/skill-tree.md
  references/routing-rules.md
```

The Reference Template contains:

```text
workflow-skill-router-template/
  README.md
  MANIFEST.md
  skills/
    workflow-skill-router/
    .system/
    <public-safe skill folders>
```

The Reference Template keeps the installable `skills/` tree and removes non-essential per-skill README files. The root package README and manifest are still included.

The Reference Template is public-safe. It is generated from a real `.codex/skills` folder, excludes organization-specific skills, and omits sensitive lines from otherwise public skill files. The [Template Skill Catalog](/Workflow-skill-router/examples/template-skill-catalog/) turns the included skills into practical routes so you can understand the pattern before designing your own router.

## Skills Included In The Reference Template

### Router And Codex System Tools

These skills help install, create, maintain, and route Codex skills. This group also includes the router itself.

- `.system/imagegen`
- `.system/openai-docs`
- `.system/plugin-creator`
- `.system/skill-creator`
- `.system/skill-installer`
- `workflow-skill-router`

### Requirements, Planning, Execution, And Handoff

These skills support requirement clarification, task decomposition, implementation plans, branch completion, handoffs, and steady engineering habits.

- `requirements-clarity`
- `executing-plans`
- `session-handoff`
- `finishing-a-development-branch`
- `commit-work`
- `receiving-code-review`
- `karpathy-guidelines`
- `writing-clearly-and-concisely`

### Architecture, API, Backend, And Database

These skills cover system design, API contracts, OpenAPI and TypeScript sync, C#/.NET, database schema work, SQL, and performance tuning.

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

### Frontend, Vue, UI, And Design Systems

These skills support frontend implementation, Vue Composition API, UI polish, design systems, Storybook, Tailwind tokens, screenshot-to-code work, and visual redesigns.

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

### DevOps, Local Development, And Dependency Management

These skills help with Docker Compose, local service stacks, CI/CD, cloud and deployment thinking, and dependency updates.

- `devops-engineer`
- `docker-compose-local-dev-skill`
- `dependency-updater`

### Testing, Debugging, Browser, And Quality Verification

These skills cover systematic debugging, Playwright, QA test planning, regression checks, and real browser verification.

- `systematic-debugging`
- `playwright`
- `qa-test-planner`

### Documentation, Diagrams, Files, And Specification Work

These skills support technical documentation, user-facing docs, Mermaid/C4 diagrams, PDF work, specification mining, coauthoring, and file organization.

- `code-documenter`
- `doc-coauthoring`
- `mermaid-diagrams`
- `pdf`
- `spec-miner`
- `file-organizer`
- `agent-md-refactor`

### Product, Brand, Visuals, And Cross-Platform Apps

These skills support brand voice, banners, visual design, Flutter apps, and more product-facing or promotional work.

- `brand`
- `banner-design`
- `design`
- `flutter-expert`

The Reference Template intentionally does not list excluded private skill folder names. Use this list as a public-safe reference catalog, then add or remove skills for your own agent environment.

## Rebuild locally

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

The package builder refuses to use an implicit local skills directory. It also requires at least one private filter unless you explicitly pass `--allow-no-private-filters` after auditing the source directory.

## Source

- [View `downloads/` on GitHub](https://github.com/eric861129/Workflow-skill-router/tree/main/downloads)
- [View Template Skill Catalog source](https://github.com/eric861129/Workflow-skill-router/tree/main/examples/template-skill-catalog)
- [View package builder script](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/package-downloads.py)
- [View template manifest](https://github.com/eric861129/Workflow-skill-router/blob/main/downloads/workflow-skill-router-template-manifest.md)
- [Download Reference Template](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template-clean.zip)
- [Download Full source archive](https://github.com/eric861129/Workflow-skill-router/raw/main/downloads/workflow-skill-router-template.zip)
- [View starter source](https://github.com/eric861129/Workflow-skill-router/tree/main/starter/workflow-skill-router)
