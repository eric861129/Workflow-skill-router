# Contributing

Thanks for helping improve Workflow Skill Router.

The best contributions are concrete routing scenarios. A useful issue or PR should include:

- the user request
- the available skills
- the route the agent chose
- the route you expected
- the conflict rule or example that would prevent the mistake next time

## Contribution Types

- New example router for a company-style workflow.
- New recipe for a common routing pattern.
- New public-safe route case in `route-cases/*.json`.
- Validator improvement.
- Documentation improvement.
- Routing failure report with reproducible inputs.

## Route Case Submissions

Route cases are the preferred small contribution for new contributors. They feed the public Routing Gallery and generated evaluator scenarios.

Use one JSON file per case:

- path: `route-cases/<kebab-case-id>.json`
- `id`: must match the filename
- `domain` and `tags`: lowercase kebab-case
- `route.primary`: exactly one primary skill
- `route.supporting`: zero to three supporting skills
- selected skills total: max 4
- `omitted_skills`: skills that look tempting but should not be selected
- `public_safety`: all checks must be `true`

Before submitting, make the case fictional. Replace real customer, school, company, host, local path, branch, token, and repository details with public-safe placeholders.

Recommended review order:

1. Open a route case issue with the expected route and omitted skills.
2. Add or update one file under `route-cases/`.
3. Run the route-case validator and generator check.
4. If the case exposes a new class of routing behavior, add a benchmark scenario and prediction.

See `docs/contributor-guide-route-examples.md` for the full schema and examples.

## Privacy Rules

Do not include:

- private repository paths
- internal project names
- customer names
- hostnames, secrets, tokens, or domains
- regulated data
- deployment branch names from a real organization

Use placeholders such as `Acme Corp`, `Customer Portal`, `Internal Admin`, `Revenue Platform`, and `Operations Dashboard`.

## Validation

Run the validation flow before opening a PR:

```bash
python scripts/validate-router.py --self-test
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/scan-skills.py ./sample-skills --out /tmp/skill-index.json --markdown /tmp/skill-index.md --warnings /tmp/skill-warnings.md --fail-on-private --fail-on-duplicates
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report.md --json-report /tmp/routing-report.json --fail-on-violations --strict
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
python scripts/render-routing-metrics-trend.py --check
python -m unittest discover -s tests
python scripts/smoke-release-assets.py --downloads-dir downloads --work-dir /tmp/wsr-release-smoke
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

