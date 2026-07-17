# Scripts

The release-critical Python scripts use the standard library and run from a fresh clone. Site and MCP reference generation use the pinned Node.js workspaces documented in their package manifests.

## `validate-router.py`

Validates a workflow-skill-router package structure.

```bash
python scripts/validate-router.py starter/v2/workflow-skill-router
```

Public-readiness audit:

```bash
python scripts/validate-router.py --public-readiness .
```

Exit code is non-zero when the V2 SKILL contract, Plugin/MCP surface, governance files, bilingual site entrypoints, or public-tree policy fails.

Private marker strings for local or private CI scans can be injected without committing them:

```bash
WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS="marker-one;marker-two" python scripts/validate-router.py --public-readiness .
```

## `check-markdown-links.py`

Checks rendered local links and media references in Markdown and MDX files. Fenced code blocks, external URLs, mailto links, and pure anchors are ignored.

```bash
python scripts/check-markdown-links.py .
```

## Generated V2 contracts

```bash
python scripts/build-v2-demo-data.py --check
node scripts/build-mcp-reference-data.mjs --check
```

These checks reject hand-authored Demo decisions and MCP reference drift.

## `run-v2-benchmark.py`

Runs the V2 paired benchmark harness. Reference-driver output is deterministic contract evidence only; a Behavior run needs explicit quota authorization and trusted review.

```bash
python scripts/run-v2-benchmark.py \
  --suite full \
  --evidence-class reference-driver \
  --adapter-executable python \
  --adapter-arg evaluation/v2/reference_driver.py \
  --repeats 3 \
  --output-dir dist/evaluation/v2/reference
```

## `build-release-artifacts.py`

Builds deterministic Plugin and SKILL archives, channels, checksums, SPDX SBOM, and provenance outside Git.

```bash
python scripts/build-release-artifacts.py --output-dir dist/release --check-determinism
```

## CI Usage

The repository validation workflow runs:

```bash
python scripts/validate-router.py --self-test
python scripts/validate-router.py starter/v2/workflow-skill-router
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
python scripts/build-v2-demo-data.py --check
node scripts/build-mcp-reference-data.mjs --check
python -m unittest discover -s tests
```
