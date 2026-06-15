# v1.1.0 — Routing Evaluation, Skill Inventory Scanner, and CI Quality Gates

Workflow Skill Router v1.1.0 adds repeatable quality checks around skill routing. This release turns the project from a starter/template package into a small, dependency-free framework for inventorying skills, evaluating routing decisions, and validating changes in CI.

## Highlights

- Added routing evaluation framework with JSONL scenarios and predictions.
- Added 30 example routing scenarios and a generated example report.
- Added dependency-free skill inventory scanner.
- Added generated skill index, scan warnings, and suggested skill tree examples.
- Added unit tests for the evaluator and scanner.
- Added GitHub Actions validation workflow.
- Updated README, docs, routing metrics guide, evaluation guide, scanner guide, and site proof messaging.

## Validation

Run:

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py examples/template-skill-catalog
python scripts/audit-public-readiness.py .

python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md \
  --warnings /tmp/skill-warnings.md \
  --suggest-tree /tmp/suggested-skill-tree.md \
  --fail-on-private \
  --fail-on-duplicates

python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations \
  --strict

python -m unittest discover -s tests
```

Expected:

```text
OK: workflow-skill-router passed validation
OK: template-skill-catalog passed validation
OK: public-readiness audit passed
19 tests pass
```

## Positioning Notes

This release ships with 30 example routing scenarios, a dependency-free skill inventory scanner, a routing evaluation harness, and CI quality gates for validation, scanning, evaluation, and unit tests.

It is designed for explainable, bounded, public-safe workflow skill routing. The example benchmark is a starting point for teams to adapt, not a claim that every router or catalog will score perfectly in production.
