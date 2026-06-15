# Skill Inventory Scanner

`scripts/scan-skills.py` scans skill markdown files and generates a machine-readable catalog plus human-readable summaries.

## What It Scans

The scanner looks for:

- `SKILL.md` files under the supplied directories
- ordinary `.md` skill files directly inside a supplied scan root

It ignores common build and dependency folders such as `.git`, `node_modules`, `.venv`, `dist`, `build`, `site`, `.next`, and `coverage`.

## Metadata Fields

Supported frontmatter fields:

- `id`
- `skill_id`
- `name`
- `description`
- `summary`
- `domains`
- `stages`
- `triggers`
- `exclusions`
- `dependencies`
- `tags`
- `owner`
- `visibility`
- `version`

The scanner also accepts common nested metadata aliases such as `metadata.domain`, `metadata.scope`, `metadata.triggers`, and `metadata.related-skills`.

## Fallback Rules

When frontmatter is missing:

- `skill_id` falls back to the folder name for `SKILL.md`, or the file name for root-level `.md` files
- `name` falls back to the first H1, then the folder or file name
- `description` falls back to the first non-empty paragraph

Missing metadata does not fail the scan. It produces quality warnings instead.

## Warning Types

Quality warnings include:

- duplicate `skill_id`
- duplicate `name`
- short or missing description
- missing triggers
- missing exclusions
- missing domains
- missing stages
- sparse tags
- heuristic overlap between domains, triggers, and tags

Public-safety warnings include:

- email addresses
- private or loopback IP addresses
- localhost URLs
- internal domain patterns such as `.local`, `.internal`, and `intranet`
- token-like strings
- secret, password, credential, API key, or access token terms
- local home paths such as `C:\Users\name\` or `/Users/name/`

Public-safety findings are warnings by default. Use `--fail-on-private` when you want them to fail CI.

## Suggested Skill Tree

`--suggest-tree` groups skills by `domains` and `stages`. If metadata is missing, the skill appears under `Uncategorized` and in the metadata gaps section.

The overlap detection and suggested tree are deterministic heuristics. They are not semantic analysis and do not use embeddings or external services.

## CLI Examples

Generate all reports:

```bash
python scripts/scan-skills.py ./sample-skills \
  --out references/skill-index.example.json \
  --markdown references/skill-index.example.md \
  --warnings references/skill-scan-warnings.example.md \
  --suggest-tree references/suggested-skill-tree.example.md
```

Scan multiple catalogs:

```bash
python scripts/scan-skills.py ./sample-skills ./starter/workflow-skill-router \
  --out /tmp/skill-index.json \
  --markdown /tmp/skill-index.md
```

Fail CI on duplicate ids:

```bash
python scripts/scan-skills.py ./sample-skills \
  --out /tmp/skill-index.json \
  --fail-on-duplicates
```

Print Markdown to stdout:

```bash
python scripts/scan-skills.py ./sample-skills --format markdown
```
