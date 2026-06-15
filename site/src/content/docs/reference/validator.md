---
title: Validation Toolchain
description: Validate router structure, public readiness, skill inventory, routing quality, and tests before publishing.
---

Workflow Skill Router includes a dependency-free validation toolchain. Use it before publishing a router repo, release, or public template package.

## 1. Validate router structure

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
```

Expected:

```text
OK: workflow-skill-router passed validation
OK: template-skill-catalog passed validation
```

This checks `SKILL.md`, required reference files, route `Primary:` markers, max skill count, example README files, and placeholder policy.

## 2. Audit public readiness

```bash
python scripts/audit-public-readiness.py .
```

Expected:

```text
OK: public-readiness audit passed
```

The audit checks community files, downloads, template catalog/manifest parity, site entrypoints, stale examples, mojibake, replacement characters, and hidden edit-link UI text.

The legacy validator flag remains available:

```bash
python scripts/validate-router.py --public-readiness .
```

## 3. Scan the skill catalog

```bash
python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md \
  --warnings /tmp/skill-warnings.md \
  --suggest-tree /tmp/suggested-skill-tree.md \
  --fail-on-private \
  --fail-on-duplicates
```

Use `--fail-on-private` and `--fail-on-duplicates` for release gates. The scanner writes a machine-readable index, Markdown summary, warnings report, and suggested skill tree.

## 4. Evaluate routing quality

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations \
  --strict
```

Add `--strict` when primary mismatches or missing expected supporting skills should fail CI.

## 5. Run unit tests

```bash
python -m unittest discover -s tests
```

The test suite covers the evaluator and scanner with standard-library `unittest`.

## Lighthouse / Accessibility audit

Use this before a public launch to score the generated Starlight site:

```bash
cd site
npm run audit:lighthouse
```

Expected:

```text
OK: Lighthouse audit passed. Reports written to lighthouse-reports
```

The audit builds the site, serves `site/dist` locally, runs Lighthouse on key English and Traditional Chinese pages, and writes JSON/HTML reports to `site/lighthouse-reports/`.

## Public URL / HTTPS smoke test

The public site intentionally uses the project path `https://huangchiyu.com/Workflow-skill-router/`. Do not add a repo-level `CNAME` file unless the project moves to a dedicated custom domain.

GitHub Pages API can still report `cname=null` or `https_enforced=false` for this setup. The publishing gate is live visitor behavior:

```bash
curl -fsS --head https://huangchiyu.com/Workflow-skill-router/
curl -fsS -I -L http://huangchiyu.com/Workflow-skill-router/
```

Expected: HTTPS returns `200`, and HTTP resolves to the HTTPS project path.

## Source

- [View `scripts/validate-router.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/validate-router.py)
- [View `scripts/audit-public-readiness.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/audit-public-readiness.py)
- [View `scripts/scan-skills.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/scan-skills.py)
- [View `scripts/evaluate-routing.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/evaluate-routing.py)
- [View the evaluation examples](https://github.com/eric861129/Workflow-skill-router/tree/main/evaluation)
