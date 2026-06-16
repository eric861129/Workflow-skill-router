# v1.3.1 - Public Safety And Launch Polish

`v1.3.1` is a patch release focused on public launch readiness. It tightens public-safety validation, replaces the heavy demo embed with lightweight video assets, refreshes social preview material, and documents dependency governance for the site tooling.

## Highlights

- Removed hard-coded private markers from the public validator source.
- Added `WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS` for local or private CI marker injection.
- Made public-readiness scan the validator source itself.
- Added a standard-library Markdown/MDX local link checker and wired it into CI.
- Replaced the showcase GIF embed with MP4/WebM video plus poster and GIF fallback.
- Added regenerated social preview images for the site and GitHub repository settings.
- Added launch copy for GitHub Discussions, Dev.to, Reddit, and Hacker News.
- Added dependency governance notes for the Lighthouse dev-tooling audit advisory.

## Validation

Expected release gate:

```bash
python scripts/validate-router.py --self-test
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/scan-skills.py ./sample-skills --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report-v1.3.1.md --json-report /tmp/routing-report-v1.3.1.json --fail-on-violations --strict
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
python scripts/render-routing-metrics-trend.py --check
python -m unittest discover -s tests
python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir /tmp/wsr-release-smoke-v1.3.1
cd site
npm ci
npm run assets:demo:check
npm run assets:social:check
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
npm audit --omit=dev --audit-level=moderate
```

## Release Assets

This release keeps the existing tracked download archives:

- `workflow-skill-router-blank.zip`
- `workflow-skill-router-template-clean.zip`
- `workflow-skill-router-template.zip`
- `workflow-skill-router-template-manifest.md`

No routing behavior or release packaging contract changes are included.

## Notes

- Full dev `npm audit` may still report the monitored Lighthouse/Sentry/OpenTelemetry advisory. See `docs/dependency-governance.md`.
- The GitHub repository social preview should be manually updated with `docs/assets/workflow-skill-router-social-preview.png` after merge.
