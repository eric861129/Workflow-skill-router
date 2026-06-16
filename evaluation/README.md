# Routing Evaluation

Routing evaluation turns skill selection into something you can inspect, compare, and regress-test. Instead of relying on a few remembered examples, you keep a JSONL benchmark of tasks and expected routes, then compare a router's predictions against it.

## Concepts

- `scenarios.example.jsonl` describes the benchmark tasks and the expected route.
- `predictions.example.jsonl` describes what a router actually selected for each scenario.
- `report.example.md` is a readable report generated from the two files.
- `route-cases.generated.jsonl` is generated from public route cases for gallery-linked evaluation.
- `metrics-history.jsonl` records release-level trend metrics.
- `schema.md` documents the JSONL fields and normalization rules.

Use scenarios for stable expectations. Use predictions for the current router output. Keeping them separate makes it easy to compare two router versions against the same benchmark.

## Run The Example

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report evaluation/report.example.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations
```

Add `--strict` when primary mismatches or missing expected supporting skills should fail CI.

## Create Your Own Scenarios

The public example benchmark currently targets 80 scenarios. Keep it between 50 and 100 records so it stays broad enough to catch regressions and small enough to review.

Start with real routing decisions that matter:

- frontend regressions after API changes
- backend contract changes that affect generated clients
- CI failures and test repairs
- release preparation and public-readiness checks
- documentation-only tasks that should not trigger implementation skills
- large tasks that should be split into stages

Each scenario should name one expected primary skill, a small supporting set, forbidden skills that must not be selected, and a `max_skills` limit. Keep `max_skills` at 4 or lower unless the task is explicitly staged.

## Generate Predictions

You can create predictions manually, or ask an agent to route each scenario and emit JSONL in the documented prediction schema. Good prediction explanations are short, concrete, and tied to why the selected skills are enough.

## Metrics

- `Primary Accuracy`: how often the selected primary skill matches.
- `Supporting Recall`: how many expected supporting skills were selected.
- `Supporting Precision`: how many selected supporting skills were expected.
- `Exact Route Match Rate`: primary and supporting set both match exactly.
- `Forbidden Skill Violation Rate`: selected route includes forbidden skills.
- `Max Skill Count Violation Rate`: route exceeds the scenario limit.
- `Over-routing Rate`: selected route is larger than expected or exceeds the limit.
- `Average Selected Skill Count`: average selected primary plus supporting count.
- `Route Explanation Present Rate`: predictions with non-empty explanations.

See [`docs/routing-metrics.md`](../docs/routing-metrics.md) for detailed definitions and improvement guidance.
See [`docs/routing-metrics-trends.md`](../docs/routing-metrics-trends.md) for the release-level trend history.

## Route Case Generated Scenarios

Public route cases live in `route-cases/*.json`. They generate gallery data and additional evaluation scenarios:

```bash
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py
python scripts/build-route-gallery.py --check
```

Add a hand-authored benchmark scenario when a route case introduces a new behavior that should become a release gate. Keep generated route-case scenarios as gallery-linked coverage.

## CI Usage

Use a tolerant gate while building the benchmark:

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --json-report /tmp/routing-report.json \
  --fail-on-violations
```

Use a strict gate once the benchmark is stable:

```bash
python scripts/evaluate-routing.py \
  --scenarios evaluation/scenarios.example.jsonl \
  --predictions evaluation/predictions.example.jsonl \
  --report /tmp/routing-report.md \
  --strict \
  --fail-on-violations
```

## Avoid Over-routing

Over-routing usually means the router selected skills that are related but not necessary. Add scenarios for tiny docs edits, single-layer bugs, and forbidden-skill boundaries. These cases keep the router honest when new skills are added to the catalog.

## Use Forbidden Skills

Forbidden skills are boundary tests. They are useful when a task is close to another domain but should not activate it. For example, a metric documentation task can forbid backend and database skills, while a frontend API regression can forbid database migration skills.
