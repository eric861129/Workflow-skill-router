# Monthly Release Cadence

Workflow Skill Router uses a monthly release train for public quality improvements. Patch releases can still ship for broken assets, security fixes, or documentation regressions.

## Week 1: Triage

- Review route case issues and routing failure reports.
- Confirm each proposed case is public-safe.
- Label accepted route cases by domain and benchmark impact.
- Close or redirect issues that require private context.

## Week 2: Benchmark

- Add accepted route cases to `route-cases/`.
- Add benchmark scenarios for new routing behavior.
- Update predictions and run strict evaluation.
- Add one row to `evaluation/metrics-history.jsonl`.

## Week 3: Site And Visual QA

- Regenerate gallery and metrics trend data.
- Review English and Traditional Chinese documentation entry points.
- Run Playwright smoke and visual checks.
- Run Lighthouse before release, but keep it outside the fastest PR gate when needed.

## Week 4: Release

- Update `CHANGELOG.md`.
- Write the release notes file under `docs/`.
- Confirm current tracked download assets still pass smoke tests.
- Merge through PR after CI is green.
- Create the annotated tag and GitHub Release.
- Verify Pages deploy and release assets after publication.

## Release Gate

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .
python scripts/scan-skills.py ./sample-skills --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report.md --json-report /tmp/routing-report.json --fail-on-violations --strict
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
python scripts/render-routing-metrics-trend.py --check
python -m unittest discover -s tests
```
