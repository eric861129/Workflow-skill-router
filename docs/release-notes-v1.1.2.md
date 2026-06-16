# v1.1.2 - Public Minimum Release Sync

Workflow Skill Router v1.1.2 is a small public-readiness patch that syncs the latest `main` branch with a fresh release and makes the public release checks easier to trust.

## Highlights

- Synced the patch release with the latest README, download, and site copy on `main`.
- Added a README package selector so new visitors can choose Blank Router, Reference Template, or Full source archive without guessing.
- Added release asset smoke testing for the downloadable zip packages and manifest.
- Added the documentation site build to the main validation workflow.
- Documented the v1.1.1 public launch polish in the changelog.

## Validation

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .
python scripts/scan-skills.py ./sample-skills --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report.md --json-report /tmp/routing-report.json --fail-on-violations --strict
python -m unittest discover -s tests
python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir /tmp/wsr-release-smoke-v1.1.2
cd site && npm ci && npm run build
```

## Download Assets

- `workflow-skill-router-blank.zip`: installable blank starter.
- `workflow-skill-router-template-clean.zip`: cleaner installable reference package.
- `workflow-skill-router-template.zip`: full public-safe reference package.
- `workflow-skill-router-template-manifest.md`: package manifest and sanitization summary.
