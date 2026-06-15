# Workflow Skill Router

> Help multi-skill AI agents choose the right workflow before they start working.

Workflow Skill Router is an **AI Agent skill routing pattern**. It helps agents select a small, explainable set of skills for each task instead of loading every related capability.

## The Problem

As agents gain more skills, capability becomes less of a constraint than selection quality:

- API work may involve architecture, backend, database, tests, docs, and SDK generation.
- Frontend work may involve UI design, framework knowledge, browser inspection, Playwright, accessibility, and QA.
- GitHub work may need a live connector, but also code review reasoning and CI diagnosis.

Without routing, an agent often treats "related" as "needed."

## The Pattern

Use a vertical decision model:

```text
Task nature
  -> Work stage
    -> Technical domain
      -> 1 primary skill + up to 3 supporting skills
```

The router does three things:

1. Classify the task.
2. Select the smallest sufficient skill set.
3. Explain why those skills were selected.

It does not replace the selected skills. It routes to them.

## Output Contract

Complex task:

```text
Route: task nature > work stage > technical domain
Use SKILL: primary-skill, supporting-skill, supporting-skill
Reason: one short sentence per SKILL
```

Simple task:

```text
No extra routing needed: reason
```

## Quickstart

Website: `https://huangchiyu.com/Workflow-skill-router/`
Traditional Chinese site: `https://huangchiyu.com/Workflow-skill-router/zh-tw/`

Copy the starter:

```text
starter/workflow-skill-router/
```

For Codex on Windows, copy it to:

```text
C:\Users\<you>\.codex\skills\workflow-skill-router
```

Then use the prompt in [prompts/agent-prompt.en.md](prompts/agent-prompt.en.md) to ask your agent to inventory its available skills and fill:

```text
workflow-skill-router/
  SKILL.md
  references/
    skill-tree.md
    routing-rules.md
  agents/
    openai.yaml
```

Validate the result:

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

## Downloadable Skill Packages

- [Blank SKILL package](downloads/workflow-skill-router-blank.zip): install this when you want an empty router and your own skill tree.
- [Template SKILL package](downloads/workflow-skill-router-template.zip): install or inspect this when you want a public-safe export of the maintainer's real local Codex skills catalog.
- [Template manifest](downloads/workflow-skill-router-template-manifest.md): included skill folders, excluded private skill count, and sanitization summary.

Rebuild the packages:

```bash
python scripts/package-downloads.py --skills-root <path-to-local-codex-skills> --exclude-prefix <private-prefix> --exclude-name <private-skill-name> --private-marker <private-text-marker>
```

The package builder refuses to use an implicit local skills directory. It also requires at least one private filter unless you explicitly pass `--allow-no-private-filters` after auditing your source directory.

The template package is generated from a real local `.codex/skills` folder. It includes the sanitized `workflow-skill-router` and all public skills used in practice, while excluding private organization-specific skills.

## Practical Examples

### API and frontend contract sync

```text
Route: API / Contract lifecycle > Backend-to-frontend sync
Use SKILL: api-designer, openapi-contract-generation-skill, openapi-to-typescript, build-web-apps:frontend-testing-debugging
Reason: api-designer stabilizes the endpoint; openapi-contract-generation-skill manages schema diff and contract generation; openapi-to-typescript updates the client types; frontend-testing-debugging verifies rendered consumption.
```

### Database migration and query risk

```text
Route: Database / Schema and performance > Migration plus query review
Use SKILL: database-schema-designer, sql-pro, database-optimizer, qa-test-planner
Reason: database-schema-designer owns migration shape; sql-pro reviews SQL correctness; database-optimizer checks query plans; qa-test-planner defines regression coverage.
```

### Browser-only frontend bug

```text
Route: Frontend / Debugging > Browser reproduction
Use SKILL: build-web-apps:frontend-testing-debugging, browser:control-in-app-browser, playwright, systematic-debugging
Reason: frontend-testing-debugging maps UI symptoms to source; browser reproduces real runtime behavior; playwright captures the regression; systematic-debugging keeps the investigation causal.
```

### PR review and CI repair

```text
Route: GitHub / Review and CI > Security-sensitive PR
Use SKILL: github:github, receiving-code-review, codex-security:security-diff-scan, github:gh-fix-ci
Reason: github:github orients the PR; receiving-code-review handles comments; security-diff-scan checks auth and data exposure; gh-fix-ci diagnoses failing checks.
```

## Repository Map

- `starter/workflow-skill-router/`: blank router skill starter.
- `examples/`: working routers for generic agents, company platform scenarios, and realistic engineering workflows.
- `sample-skills/`: copyable public `SKILL.md` examples that pair with the common engineering routes.
- `downloads/`: generated blank and template SKILL zip packages.
- `recipes/`: practical route design patterns.
- `scripts/validate-router.py`: dependency-free validator.
- `scripts/package-downloads.py`: dependency-free package builder for the downloadable archives.
- `site/`: Astro Starlight website for GitHub Pages.
- `prompts/`: creation and maintenance prompts.
- `docs/`: theory, customization, and validation guidance.

## Design Principles

- Do not disable every other skill and keep only the router.
- Do not turn the router into a giant super skill.
- Select at most four skills per route.
- Prefer connector/plugin skills when live external systems are the source of truth.
- Split workflows into stages when a route needs more than four skills.
- Keep detailed examples outside `SKILL.md` so the router stays light.

## Contributing

Contributions are most useful when they include a reproducible routing scenario:

- user request
- available skill list
- expected route
- route that failed or felt noisy
- proposed conflict rule

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
