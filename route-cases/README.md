# Public Route Cases

`route-cases/*.json` is the canonical public route-case interface for Workflow Skill Router.

Each file describes one public-safe request, the expected route, omitted skills, and safety review metadata. These cases feed:

- the Routing Gallery on the documentation site,
- generated evaluator scenarios in `evaluation/route-cases.generated.jsonl`,
- community issue and pull request review.

## Required Shape

```json
{
  "id": "frontend-api-regression",
  "title": "Frontend API regression",
  "domain": "frontend",
  "task": "Fix a Vue page that renders empty data after an API response changed.",
  "context": "The backend renamed response fields and the page now shows an empty table.",
  "route": {
    "path": "Frontend / Vue / UI > Browser regression",
    "primary": "frontend-debugging-workflow",
    "supporting": ["vue-composition-patterns-skill", "api-guidelines-skill", "qa-test-planner"],
    "reason": "Start from the rendered regression, verify Vue state, API expectations, and regression coverage."
  },
  "omitted_skills": [
    {
      "skill": "database-optimizer",
      "reason": "The symptom is not a query performance problem."
    }
  ],
  "tags": ["frontend", "api", "debugging"],
  "public_safety": {
    "fictionalized": true,
    "no_private_paths": true,
    "no_secrets": true,
    "no_customer_names": true,
    "no_live_credentials": true,
    "review_notes": "Uses fictional product context only."
  }
}
```

## Validation

```bash
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
```

Rules enforced by the validator:

- `id` and filename must match and use lowercase kebab-case.
- `domain` and `tags` must use lowercase kebab-case.
- the route can select at most 4 skills total.
- `route.primary` cannot appear in `route.supporting`.
- `omitted_skills` cannot include selected skills.
- all `public_safety` checks must be true.
- case text must not contain local paths, private network addresses, private domains, or token-shaped secrets.
