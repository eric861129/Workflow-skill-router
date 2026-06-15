# Scripts

All Python scripts in this repository use the standard library and can run from a fresh clone.

## `validate-router.py`

Validates a workflow-skill-router package structure.

```bash
python scripts/validate-router.py starter/workflow-skill-router
```

Public-readiness audit:

```bash
python scripts/validate-router.py --public-readiness .
```

Exit code is non-zero when required files, router structure, route limits, placeholder policy, public-readiness checks, or catalog parity checks fail.

## `scan-skills.py`

Scans skill markdown files and writes a JSON index, Markdown summary, warnings report, and optional suggested skill tree.

```bash
python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md \
  --warnings /tmp/skill-warnings.md \
  --suggest-tree /tmp/suggested-skill-tree.md
```

Useful flags:

- `--fail-on-private`: fail when public-safety warnings are found
- `--fail-on-duplicates`: fail when duplicate skill ids or names are found
- `--format json|markdown`: print an index to stdout when no output path is supplied
- `--generated-at`: use a fixed timestamp for deterministic examples

## `evaluate-routing.py`

Evaluates route predictions against scenario expectations.

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations
```

Useful flags:

- `--fail-on-violations`: fail on forbidden skills, max skill count violations, missing predictions, or unknown predictions
- `--strict`: also fail on primary mismatches or missing expected supporting skills

## CI Usage

The repository validation workflow runs:

```bash
python scripts/validate-router.py starter/workflow-skill-router
python scripts/validate-router.py --public-readiness .
python scripts/scan-skills.py ./sample-skills --out /tmp/skill-index.json --markdown /tmp/skill-index.md --warnings /tmp/skill-warnings.md
python scripts/evaluate-routing.py --scenarios evaluation/scenarios.example.jsonl --predictions evaluation/predictions.example.jsonl --report /tmp/routing-report.md --json-report /tmp/routing-report.json --fail-on-violations
python -m unittest discover -s tests
```
