# Routing Evaluation Schema

V2 separates **Tier 0 Contract** JSONL from sealed Behavior/Outcome artifacts. `manual-required` and `review-required` are valid evidence states. A `skill-only-fallback` run cannot be promoted to `hybrid-full` by adding a `trusted` field or a local receipt file.

The evaluator reads newline-delimited JSON. Each non-empty line must be one JSON object.

## Scenario Record

```json
{
  "id": "frontend-api-regression",
  "task": "Fix a Vue page that broke after the backend API response changed.",
  "context": "The page renders empty data after a recent API contract change.",
  "expected": {
    "primary": "frontend-debugging-workflow",
    "supporting": ["api-guidelines-skill", "qa-test-planner"]
  },
  "forbidden": ["database-optimizer"],
  "max_skills": 3,
  "tags": ["frontend", "api", "debugging"],
  "notes": "Start with the rendered symptom and verify the API contract."
}
```

Required fields:

- `id`: unique kebab-case scenario id.
- `task`: user-facing task text.
- `context`: extra background. Use an empty string when not needed.
- `expected.primary`: expected primary skill id.
- `expected.supporting`: expected supporting skill ids. Use an empty array for narrow tasks.
- `forbidden`: skill ids that must not be selected. Use an empty array when not needed.
- `max_skills`: maximum selected skill count, including primary.
- `tags`: classification labels for reporting and filtering.
- `notes`: why this scenario exists.

## Prediction Record

```json
{
  "id": "frontend-api-regression",
  "selected": {
    "primary": "frontend-debugging-workflow",
    "supporting": ["api-guidelines-skill", "qa-test-planner"]
  },
  "explanation": "Start with the rendered symptom, then verify the API contract and tests.",
  "stage_split": false
}
```

Required fields:

- `id`: matching scenario id.
- `selected.primary`: selected primary skill id.
- `selected.supporting`: selected supporting skill ids.
- `explanation`: non-empty route explanation.
- `stage_split`: boolean that marks tasks that should be split into stages.

## Skill ID Normalization

The evaluator normalizes skill ids before comparison:

- trims leading and trailing whitespace
- lower-cases values
- keeps hyphens and underscores distinct

This catches case and whitespace mistakes without hiding naming drift.

## Failure Modes

Schema errors always produce a non-zero exit code. Examples include invalid JSON, duplicate ids, missing required objects, or fields with the wrong type.

`--fail-on-violations` also fails on:

- forbidden skill selection
- max skill count violation
- missing prediction
- unknown prediction id

`--strict` also fails on:

- primary mismatch
- missing expected supporting skill
