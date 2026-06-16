# v1.3.0 - Community Gallery, Metrics, And Visual QA

`v1.3.0` moves Workflow Skill Router from a useful starter toward a more mature open-source project surface: public route cases, measurable routing quality, visual site checks, and privacy-first conversion tracking.

## Highlights

- Added a public-safe Routing Gallery generated from root-level `route-cases/*.json`.
- Added route case validation, gallery data generation, and generated evaluator scenarios.
- Expanded the benchmark from 30 to 80 scenarios, including simple-task and anti-over-routing boundaries.
- Added release-level metrics history from `v1.2.0` to `v1.3.0`.
- Added a Metrics Trends documentation page.
- Added Playwright smoke tests and key visual snapshots for home, downloads, gallery, and metrics pages.
- Added disabled-by-default Plausible-compatible analytics and transparent README CTA landing pages.
- Added route case submission guidance, issue template, and monthly release cadence docs.

## Public Interfaces

- New route case schema: `route-cases/*.json`.
- New generated gallery data: `site/src/data/route-cases.generated.json`.
- New generated route-case scenarios: `evaluation/route-cases.generated.jsonl`.
- New metrics history: `evaluation/metrics-history.jsonl`.
- New site npm scripts:
  - `npm run test:site:smoke`
  - `npm run test:site:visual`
  - `npm run test:site:update-snapshots`
- New analytics env vars:
  - `PUBLIC_ANALYTICS_PROVIDER`
  - `PUBLIC_PLAUSIBLE_DOMAIN`
  - `PUBLIC_PLAUSIBLE_SCRIPT_URL`

## Validation

Expected release gate:

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .
python scripts/scan-skills.py ./sample-skills --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report-v1.3.0.md --json-report /tmp/routing-report-v1.3.0.json --fail-on-violations --strict
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
python scripts/render-routing-metrics-trend.py --check
python -m unittest discover -s tests
python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir /tmp/wsr-release-smoke-v1.3.0
cd site
npm ci
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
```

## Release Assets

This release keeps the existing tracked download assets and verifies them with the release asset smoke test:

- `workflow-skill-router-blank.zip`
- `workflow-skill-router-template-clean.zip`
- `workflow-skill-router-template.zip`
- `workflow-skill-router-template-manifest.md`

No routing behavior or release packaging contract changes are included.
