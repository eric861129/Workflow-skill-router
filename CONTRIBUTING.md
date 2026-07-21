# Contributing to Workflow Skill Router V2

Thank you for improving a router that developers can inspect, test, and trust. V2 contributions should strengthen a concrete runtime contract rather than add promotional examples or unverified model claims.

Please read [GOVERNANCE.md](GOVERNANCE.md), [SECURITY.md](SECURITY.md), and the [V2 architecture](docs/architecture/v2-overview.md) before a structural change.

## Choose a Contribution Path

### Router Core

Use `packages/router-core/` for task profiling, routing policy, phase state, consent, persistence, capability discovery, and CLI behavior. Add focused unit tests beside the affected module.

```bash
set PYTHONPATH=packages/router-core/src
python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v
```

On macOS or Linux, use `export PYTHONPATH=packages/router-core/src`.

### Plugin / MCP Runtime

Use `plugins/workflow-skill-router/` for MCP tool contracts, the bundled runtime bridge, schema validation, and Plugin packaging. Keep host authority explicit: the Plugin may report capabilities, but it must not invent permissions or silently activate an executable adapter.

```bash
python plugins/workflow-skill-router/scripts/build-runtime.py --check
cd plugins/workflow-skill-router
npm ci
npm run check
node ./scripts/smoke-plugin.mjs
```

### Model Evaluation

Use `evaluation/v2/`, `scripts/run-v2-benchmark.py`, and the related tests for model evaluation profiles, sealed cases, evidence manifests, comparison rules, and adapters.

Default CI is a **no live model** environment. It must not require Codex credentials, invoke a paid adapter, or spend quota. A behavior-evidence run requires separate maintainer authorization, a fixed attempt budget, sanitized inputs, and trusted review before its status can be promoted.

### Documentation Site

Use `site/` for the bilingual Astro/Starlight documentation site and interactive demo. English and Traditional Chinese navigation and critical guides must remain aligned.

```bash
cd site
npm ci
npm run assets:demo:check
npm run assets:social:check
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
```

### Documentation-only Changes

For a documentation-only contribution, update the relevant root document or both site locales when the public contract changes. Run:

```bash
python scripts/check-markdown-links.py .
git diff --check
```

## Local V2 Quality Gate

Before opening a pull request, run the smallest focused tests first and then the repository gate:

```bash
python scripts/validate-router.py starter/v2/workflow-skill-router
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python -I -S -B scripts/build-release-artifacts.py --output-dir dist/release --check-determinism
python -m unittest discover -s tests
node scripts/build-mcp-reference-data.mjs --check
cd site
npm ci
npm run assets:demo:check
npm run assets:social:check
npm run build
npm run test:site:smoke
```

The release workflow adds a clean-tree deterministic build, SBOM, provenance, and attestation checks. Do not generate or edit tracked download archives in a pull request.

## Reproducibility and Privacy

- Prefer one behavior change and one focused regression test per pull request.
- Include the task size, phase, available Skills, expected route, and consent state for routing failures.
- For runtime bugs, include sanitized logs and versions, never local state files.
- Never submit credentials, private prompts, customer names, internal paths, hostnames, or SQLite state databases.
- Do not label fixtures or deterministic contract tests as real model evidence.
- Do not add new V1 gallery, evaluator, metrics, or starter-generation dependencies to V2 paths.

## Pull Requests

Explain the user-visible contract, the proof you ran, and any remaining limitation. A maintainer may request architecture review for changes to schemas, state transitions, MCP tools, evaluation evidence, release artifacts, or security boundaries.
