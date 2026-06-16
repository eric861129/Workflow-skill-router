# Contributor Guide: Route Examples

Route examples are the smallest useful community contribution to Workflow Skill Router. A good route case teaches one routing decision without exposing private context.

## What to Submit

Submit a root-level JSON file under `route-cases/`.

Good cases include:

- a fuzzy but realistic developer request,
- the context that affects routing,
- one primary skill,
- zero to three supporting skills,
- skills that should be omitted and why,
- public-safety review notes.

Avoid cases that require private repository names, real customer names, internal hostnames, local filesystem paths, credentials, regulated data, or screenshots from private systems.

## Schema Checklist

- `id`: lowercase kebab-case and identical to the filename.
- `title`: short reader-facing title.
- `domain`: lowercase kebab-case, such as `api`, `frontend`, `database`, `docs`, `release`, `connector`, or `simple-task`.
- `task`: the user request.
- `context`: facts the router should consider.
- `route.path`: human-readable path from broad domain to specific workflow.
- `route.primary`: one skill id.
- `route.supporting`: list of supporting skill ids; total selected skills must be 4 or fewer.
- `route.reason`: why this route is smaller and safer than over-routing.
- `omitted_skills`: tempting skills that should not be selected, each with a reason.
- `tags`: lowercase kebab-case labels for gallery filtering.
- `public_safety`: all checklist fields must be `true`.

## Validation

Run:

```bash
python scripts/validate-route-cases.py route-cases
python scripts/build-route-gallery.py --check
```

If you changed generated gallery data, run:

```bash
python scripts/build-route-gallery.py
```

Then include the generated `site/src/data/route-cases.generated.json` and `evaluation/route-cases.generated.jsonl` changes in the same pull request.

## When to Add a Benchmark Scenario

Add a row to `evaluation/scenarios.example.jsonl` and `evaluation/predictions.example.jsonl` when the case introduces a new behavior that should stay stable across releases, such as:

- a new anti-over-routing boundary,
- a connector fallback rule,
- a public-safety decision,
- a route conflict between two plausible primary skills,
- a new class of forbidden-skill mistake.

Keep benchmark records public-safe for the same reasons as route cases.
