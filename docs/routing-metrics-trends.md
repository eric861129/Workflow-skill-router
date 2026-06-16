# Routing Metrics Trends

This public history tracks the small benchmark used by Workflow Skill Router releases. It is intentionally lightweight: the goal is to show direction, coverage, and violation rates without claiming model-wide performance.

| Version | Date | Scenarios | Primary accuracy | Supporting recall | Supporting precision | Forbidden violations | Max skill violations | Over-routing |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1.2.0 | 2026-06-16 | 30 | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |
| v1.3.0 | 2026-06-16 | 80 | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% |

## How to update

1. Run `python scripts/evaluate-routing.py` against the release benchmark.
2. Add one row to `evaluation/metrics-history.jsonl`.
3. Run `python scripts/render-routing-metrics-trend.py`.
4. Commit the generated site data and this markdown summary.

The history keeps the existing evaluator JSON report compatible. Trend fields are duplicated in snake_case so the documentation site can render them without parsing report labels.
