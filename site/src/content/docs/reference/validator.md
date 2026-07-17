---
title: Validation Toolchain
description: Validate the V2 SKILL, public surface, generated contracts, release packages, and tests before publishing.
---

Workflow Skill Router includes a local-first validation toolchain. Deterministic CI does not require Codex credentials or live-model quota.

## 1. Validate router structure

```bash
python scripts/validate-router.py starter/v2/workflow-skill-router
```

Expected:

```text
OK: workflow-skill-router passed validation
```

This checks the V2 frontmatter, routing/Goal/evaluation references, routing envelopes, Explicit Skill Lock, runtime capability wording, and honest Skill-only fallback label.

## 2. Audit public readiness

```bash
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
```

Expected:

```text
OK: public-readiness audit passed
```

These checks enforce the V2 public tree, governance files, Plugin/MCP and SKILL-only entrypoints, English/Traditional Chinese route parity, local links, UTF-8 safety, and the reviewed V1 removal boundary.

## 3. Verify generated contracts

```bash
python scripts/build-v2-demo-data.py --check
node scripts/build-mcp-reference-data.mjs --check
```

The first command proves the interactive Demo was generated from Router Core inputs. The second proves the public MCP reference matches the ten real tool contracts and readiness matrix.

## 4. Evaluate routing quality

```bash
python scripts/run-v2-benchmark.py \
  --suite full \
  --evidence-class reference-driver \
  --adapter-executable python \
  --adapter-arg evaluation/v2/reference_driver.py \
  --repeats 3 \
  --output-dir dist/evaluation/v2/reference
```

Reference-driver output proves only the harness contract. Behavior evidence requires a separately authorized fresh-model run and a validated 36-attempt report; without it, the public status remains `manual-required`.

## 5. Run unit tests

```bash
$env:PYTHONPATH = "packages/router-core/src"
python -m unittest discover -s packages/router-core/tests -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
```

The suites cover Router Core, Plugin contracts, evaluation isolation, release reproducibility, installation smoke, public governance, and documentation policy.

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
- [View `scripts/run-v2-benchmark.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/run-v2-benchmark.py)
- [View `scripts/build-release-artifacts.py` on GitHub](https://github.com/eric861129/Workflow-skill-router/blob/main/scripts/build-release-artifacts.py)
- [View the V2 evaluation contracts](https://github.com/eric861129/Workflow-skill-router/tree/main/evaluation/v2)
