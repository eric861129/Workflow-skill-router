# Sample Skills

These are copyable `SKILL.md` examples that pair with `examples/template-skill-catalog`, the scanner examples in `references/`, and the routing evaluation benchmark in `evaluation/`.

Most folders are complete public-safe skill folders copied from a real local Codex skill catalog. A few folders are intentionally rewritten into shorter public examples when the original local skill contained organization-specific context.

They are all intentionally generic:

- no organization names
- no private paths
- no secrets or hostnames
- no product-specific architecture

Use them as references for how to write a practical skill body, not as a required skill catalog.

Generate a catalog from these examples:

```bash
python scripts/scan-skills.py ./sample-skills \
  --out references/skill-index.example.json \
  --markdown references/skill-index.example.md \
  --warnings references/skill-scan-warnings.example.md \
  --suggest-tree references/suggested-skill-tree.example.md
```

## Included Skills

- `architecture-designer`
- `c4-architecture`
- `code-documenter`
- `commit-work`
- `csharp-developer`
- `database-optimizer`
- `dependency-updater`
- `dotnet-core-expert`
- `executing-plans`
- `finishing-a-development-branch`
- `frontend-design`
- `karpathy-guidelines`
- `openapi-to-typescript`
- `playwright`
- `qa-test-planner`
- `receiving-code-review`
- `spec-miner`
- `systematic-debugging`

## Public Example Rewrites

These folders are concise public versions of practical local skills whose original private versions referenced internal systems or organization-specific context:

- `api-guidelines-skill`
- `docker-compose-local-dev-skill`
- `frontend-debugging-workflow`
- `requirements-clarity`
- `vue-composition-patterns-skill`
