# Validation Checklist

Use this checklist before publishing or relying on a workflow skill router.

## Structure

- [ ] `SKILL.md` exists.
- [ ] `SKILL.md` has YAML frontmatter.
- [ ] `name` is hyphen-case.
- [ ] `description` says when to use the skill, not the whole workflow.
- [ ] `references/skill-tree.md` exists.
- [ ] `references/routing-rules.md` exists.
- [ ] Reference files are one level away from `SKILL.md`.
- [ ] Starter placeholder skills are marked as placeholder-only or replaced with real template skills.

## Routing Quality

- [ ] Every route follows `task nature -> work stage -> technical domain`.
- [ ] Every route chooses 1-4 skills.
- [ ] Each route has one clear primary skill.
- [ ] Supporting skills cover distinct jobs.
- [ ] Broad meta skills are not default choices.
- [ ] Connector tasks prefer connector/plugin skills.
- [ ] Routing scenarios cover forbidden-skill and over-routing boundary cases.
- [ ] `max_skills` is set to the smallest useful route size.
- [ ] Predictions include a concrete non-empty explanation.

## Conflict Rules

- [ ] Local vs plugin priority is documented.
- [ ] Browser automation choices are documented.
- [ ] Review vs GitHub connector choices are documented.
- [ ] File-format connector choices are documented.
- [ ] User-explicit skill requests are respected.

## Scenario Tests

Test at least these prompts:

```text
Design a new backend API with database schema and test plan.
```

Expected: API, backend, database, QA skills.

```text
Debug a browser-only login failure in a Vue admin app.
```

Expected: frontend debugging, browser, systematic debugging, possibly backend.

```text
Write a technical workflow document with Mermaid diagrams.
```

Expected: documentation, writing, diagram skills.

```text
Address unresolved GitHub PR review comments.
```

Expected: GitHub connector plus review reasoning.

```text
Summarize recent Teams messages and draft a reply.
```

Expected: Teams connector skills.

```text
List files in this folder.
```

Expected: no extra routing.

## Failure Signals

- The router picks more than 4 skills for a single task.
- The router triggers on simple one-line tasks.
- The router selects generic docs skills for file-format tasks that need rendering.
- The router ignores user-named skills.
- The router duplicates equivalent local and plugin skills without a reason.

## Fixes

- Split large routes into smaller work stages.
- Move detailed mappings from `SKILL.md` to `skill-tree.md`.
- Add a conflict rule for repeated mistakes.
- Narrow the frontmatter description if the router triggers too often.

## Public-Readiness Gate

Before publishing a repo, release, or template package, run:

```bash
python scripts/audit-public-readiness.py .
```

Expected:

```text
OK: public-readiness audit passed
```

This checks community files, downloads, site entrypoints, stale examples, placeholder policy, mojibake, and hidden edit-link UI text.

## Routing Evaluation Gate

Before changing router rules or publishing a new template, run:

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations
```

Expected:

```text
exit code 0, no forbidden skill violations, no max skill count violations, no missing predictions
```

Add `--strict` when primary mismatches and missing expected supporting skills should block the change.

## Skill Inventory Gate

Before relying on a skill catalog, run:

```bash
python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md \
  --warnings /tmp/skill-warnings.md \
  --suggest-tree /tmp/suggested-skill-tree.md
```

Review warnings for duplicate ids, sparse metadata, overlap, and public-safety markers.

## Lighthouse / Accessibility Gate

Before a public launch, run the formal website quality audit:

```bash
cd site
npm run audit:lighthouse
```

Expected:

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

Default thresholds are performance 70, accessibility 95, best-practices 90, and SEO 90. Local JSON and HTML reports are written to `site/lighthouse-reports/` and are intentionally ignored by git.

## Public URL / HTTPS Gate

This repo publishes the site as a project path under `https://huangchiyu.com/Workflow-skill-router/`. Do not add a repo-level `CNAME` file unless the project intentionally moves to a dedicated custom domain, because a CNAME can try to claim the whole host instead of only this path.

GitHub Pages API may report `cname=null` or `https_enforced=false` for this project-path setup. Treat the live visitor behavior as the publishing gate:

```bash
curl -fsS --head https://huangchiyu.com/Workflow-skill-router/
curl -fsS -I -L http://huangchiyu.com/Workflow-skill-router/
```

Expected: HTTPS returns `200`, and HTTP resolves to `https://huangchiyu.com/Workflow-skill-router/`.

## UTF-8 / Windows Display Check

All Traditional Chinese docs and examples are stored as UTF-8. On Windows, prefer `Get-Content -Encoding UTF8`, VS Code, or `rg` when checking Chinese text. A legacy PowerShell code page can display mojibake even when the file is valid UTF-8.
