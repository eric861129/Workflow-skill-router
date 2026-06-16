# v1.2.0 - Onboarding And Adapter Notes

Workflow Skill Router v1.2.0 focuses on public onboarding quality: a clearer Blank Router path, practical troubleshooting, adapter notes for other AI coding tools, and a shareable 60-second demo.

## Highlights

- Added a complete Blank Router walkthrough that starts from the downloadable blank package and ends with validated route examples.
- Added Troubleshooting coverage for install paths, PowerShell, Python, zip extraction, validator messages, and public-readiness checks.
- Added Claude, Cursor, and Gemini adapter notes that explain how to reuse the routing contract outside Codex without claiming fixed product UI paths.
- Added a 60-second demo GIF showing fuzzy request intake, route selection, validation, and the download path.
- Updated README, Quickstart, Showcase, and the documentation sidebar so new visitors can find the next step quickly.

## Validation

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .
python scripts/scan-skills.py ./sample-skills --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report.md --json-report /tmp/routing-report.json --fail-on-violations --strict
python -m unittest discover -s tests
python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir /tmp/wsr-release-smoke-v1.2.0
cd site && npm ci && npm run build
```

## Download Assets

This release continues to use the current public download assets:

- `workflow-skill-router-blank.zip`: installable blank starter.
- `workflow-skill-router-template-clean.zip`: clean installable reference package.
- `workflow-skill-router-template.zip`: full public-safe reference package.
- `workflow-skill-router-template-manifest.md`: package manifest and sanitization summary.
