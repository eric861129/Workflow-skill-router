# Workflow Skill Router V2 Foundations and Capability Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立不破壞 V1 的 Python 3.11+ 核心 distribution、版本化 schema registry，以及只讀 frontmatter／manifest 的安全 Runtime Capability Discovery、不可變 snapshot 與 drift detection。

**Architecture:** 先用 subprocess golden harness 凍結所有既有 CLI 的外部契約，再於單一 `workflow_skill_router` modular monolith 新增 schema 與 capability 模組。Discovery 把 provider observation 依欄位權威合併，使用 deterministic availability precedence 建立 immutable snapshot；filesystem provider 在 frontmatter 結束符號後立即停止，不碰 instruction body。

**Tech Stack:** Python 3.11+、Python standard library、`unittest`、`dataclasses`、`enum`、`hashlib`、`json`、`concurrent.futures`、JSON Schema documents（不新增 runtime validator dependency）

## Global Constraints

- 唯一 Python runtime distribution 是 `packages/router-core/`；import namespace 固定為 `workflow_skill_router.*`，不拆成多個 distribution。
- 內部分層固定為 `schemas/`、`capabilities/`、`routing/`、`workflow/`、`goals/`、`persistence/`、`evaluation/`、`cli/`；CLI canonical layout 是 `workflow_skill_router/cli/` package（不是單一 `cli.py`），未來 console entry point 固定指向 `workflow_skill_router.cli:main`；本計畫只建立前兩層與 package root。
- Core runtime 只可使用 Python 3.11+ standard library；legacy public scripts 仍須維持 fresh clone 可執行，且本階段不得 import 新 package。
- 先凍結 V1 subprocess contract，再新增 V2 code；不可修改 `scripts/*.py` 來讓 golden test 通過。
- Capability Discovery 只能讀可信 installer manifest、frontmatter 或衍生 metadata；不得讀取完整 `SKILL.md` instruction body，也不得把 metadata 文字當指令執行。若 installer manifest 提供 content digest，Discovery 只保存該「宣告 digest」及 provenance；真正 instruction body digest 必須延後到 Plan 03 已通過 Explicit Skill Lock／consent 的 lease activation 才計算與比對。
- 每個 Route 將只接受 immutable `CapabilitySnapshot` 中的 capability；snapshot、schema、event、文件與 artifact 一律 UTF-8。
- Availability precedence 固定為 `incompatible > unavailable > auth-required > unknown > stale > degraded > available`，並保留次要 reason flags。
- Cache 不得把 unavailable 提升為 available；runtime exposure／approval 以 host observation 為準，MCP health／schema 以 handshake 為準，SKILL metadata／fingerprint 以受信任 filesystem metadata 為準。
- R0／R1 可以明示 degraded stale；R2／R3 必須 fresh preflight。Warm discovery 在 1,000 capabilities 下必須小於 2 秒。
- Local-first、telemetry 預設關閉，不保存 secret、credential、私人絕對路徑或不必要的 instruction／user content。
- 基本流程必須能在 Windows、macOS、Linux 執行；測試不得依賴 PowerShell-only path semantics。
- 本計畫不建立 SQLite migration、state machine、Goal、MCP transport 或 service facade；由後續計畫消費此處的 contracts。

## Locked File Map

```text
packages/router-core/
├── pyproject.toml                              # 單一 runtime distribution 與 package data
├── src/workflow_skill_router/
│   ├── __init__.py                            # V2 alpha version
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── artifacts.py                       # ArtifactEnvelope 與 canonical JSON
│   │   ├── errors.py                          # SchemaRegistryError
│   │   ├── registry.py                        # schema_id + version + kind 分派
│   │   └── json/v2/*.schema.json              # 公開 envelope/capability/snapshot schema
│   └── capabilities/
│       ├── __init__.py
│       ├── models.py                          # immutable capability contracts
│       ├── availability.py                    # deterministic precedence
│       ├── frontmatter.py                     # header-only UTF-8 parser
│       ├── filesystem.py                      # bounded trusted-root provider
│       ├── providers.py                       # provider observation protocol
│       ├── native_host.py                     # verified host exposure/policy provider
│       ├── plugin_handshake.py                # MCP schema/health/auth provider
│       ├── agent_runtime.py                   # agent-visible skills/tools provider
│       ├── cache.py                           # degraded-only previous snapshot provider
│       ├── merge.py                           # field-level authority merge
│       ├── snapshot.py                        # deterministic immutable snapshot
│       ├── drift.py                           # typed snapshot drift
│       └── runtime_context.py                 # verified provider composition and sync result
└── tests/
    ├── compat/                                # V1 subprocess golden harness
    ├── schemas/
    └── capabilities/
```

---

### Task 1: Freeze the V1 CLI surface with a subprocess golden harness

**Files:**
- Create: `packages/router-core/tests/compat/__init__.py`
- Create: `packages/router-core/tests/compat/legacy_cli_cases.py`
- Create: `packages/router-core/tests/compat/golden_runner.py`
- Create: `packages/router-core/tests/compat/capture_legacy_cli_goldens.py`
- Create: `packages/router-core/tests/compat/test_legacy_cli_goldens.py`
- Create: `packages/router-core/tests/compat/golden/legacy-cli-v1.json`

**Interfaces:**
- Consumes: 目前 repository root 下的 `scripts/*.py`、`evaluation/*.example.jsonl`、`sample-skills/`、`route-cases/` 與既有 generated artifacts。
- Produces: `LegacyCliCase(name: str, argv: tuple[str, ...], env: Mapping[str, str], artifact_paths: tuple[str, ...])`；`run_case(case: LegacyCliCase) -> dict[str, object]`；經路徑與換行正規化的完整 stdout、stderr、exit code、artifact bytes／shape；明確更新命令 `python .../capture_legacy_cli_goldens.py --write`。

- [ ] **Step 1: Write the failing golden comparison test and immutable case table**

```python
# packages/router-core/tests/compat/legacy_cli_cases.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class LegacyCliCase:
    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    input_files: Mapping[str, str] = field(default_factory=dict)
    artifact_paths: tuple[str, ...] = ()


FIXED_GENERATED_AT = "2000-01-01T00:00:00Z"
STRICT_SCENARIO = '{"id":"strict","task":"測試","expected":{"primary":"expected","supporting":[]},"forbidden":[],"max_skills":1,"tags":[]}\n'
STRICT_MISMATCH = '{"id":"strict","selected":{"primary":"wrong","supporting":[]},"explanation":"刻意不相符","stage_split":false}\n'
VIOLATION_SCENARIO = '{"id":"violation","task":"測試","expected":{"primary":"safe","supporting":[]},"forbidden":["forbidden"],"max_skills":1,"tags":[]}\n'
VIOLATION_PREDICTION = '{"id":"violation","selected":{"primary":"forbidden","supporting":[]},"explanation":"刻意違規","stage_split":false}\n'


CASES = (
    LegacyCliCase("scan-help", ("scripts/scan-skills.py", "--help")),
    LegacyCliCase("scan-missing-path", ("scripts/scan-skills.py", "{tmp}/missing-skills")),
    LegacyCliCase(
        "scan-stdout-json",
        ("scripts/scan-skills.py", "sample-skills", "--format", "json", "--generated-at", FIXED_GENERATED_AT),
    ),
    LegacyCliCase(
        "scan-stdout-markdown",
        ("scripts/scan-skills.py", "sample-skills", "--format", "markdown", "--generated-at", FIXED_GENERATED_AT),
    ),
    LegacyCliCase(
        "scan-generated-shape",
        (
            "scripts/scan-skills.py", "sample-skills", "--out", "{tmp}/index.json",
            "--markdown", "{tmp}/summary.md", "--warnings", "{tmp}/warnings.md",
            "--suggest-tree", "{tmp}/tree.md", "--generated-at", FIXED_GENERATED_AT,
        ),
        artifact_paths=("index.json", "summary.md", "warnings.md", "tree.md"),
    ),
    LegacyCliCase("validate-help", ("scripts/validate-router.py", "--help")),
    LegacyCliCase("validate-path", ("scripts/validate-router.py", "starter/workflow-skill-router")),
    LegacyCliCase("validate-missing-path-argument", ("scripts/validate-router.py",)),
    LegacyCliCase("validate-self-test", ("scripts/validate-router.py", "--self-test")),
    LegacyCliCase("validate-public-readiness", ("scripts/validate-router.py", ".", "--public-readiness")),
    LegacyCliCase(
        "validate-public-readiness-env-marker-failure",
        ("scripts/validate-router.py", ".", "--public-readiness"),
        env={"WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS": "Workflow Skill Router"},
    ),
    LegacyCliCase("evaluate-help", ("scripts/evaluate-routing.py", "--help")),
    LegacyCliCase(
        "evaluate-generated-shape",
        (
            "scripts/evaluate-routing.py", "--scenarios", "evaluation/scenarios.example.jsonl",
            "--predictions", "evaluation/predictions.example.jsonl", "--report", "{tmp}/report.md",
            "--json-report", "{tmp}/report.json",
        ),
        artifact_paths=("report.md", "report.json"),
    ),
    LegacyCliCase(
        "evaluate-strict-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/strict-scenarios.jsonl",
            "--predictions", "{tmp}/strict-predictions.jsonl", "--report", "{tmp}/strict-report.md",
            "--strict",
        ),
        input_files={"strict-scenarios.jsonl": STRICT_SCENARIO, "strict-predictions.jsonl": STRICT_MISMATCH},
        artifact_paths=("strict-report.md",),
    ),
    LegacyCliCase(
        "evaluate-fail-on-violations-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/violation-scenarios.jsonl",
            "--predictions", "{tmp}/violation-predictions.jsonl", "--report", "{tmp}/violation-report.md",
            "--json-report", "{tmp}/violation-report.json", "--fail-on-violations",
        ),
        input_files={
            "violation-scenarios.jsonl": VIOLATION_SCENARIO,
            "violation-predictions.jsonl": VIOLATION_PREDICTION,
        },
        artifact_paths=("violation-report.md", "violation-report.json"),
    ),
    LegacyCliCase(
        "evaluate-invalid-json-failure",
        (
            "scripts/evaluate-routing.py", "--scenarios", "{tmp}/invalid.jsonl",
            "--predictions", "evaluation/predictions.example.jsonl", "--report", "{tmp}/invalid-report.md",
        ),
        input_files={"invalid.jsonl": "{not-json}\n"},
        artifact_paths=("invalid-report.md",),
    ),
    LegacyCliCase("route-cases", ("scripts/validate-route-cases.py",)),
    LegacyCliCase("gallery-check", ("scripts/build-route-gallery.py", "--check")),
    LegacyCliCase("metrics-check", ("scripts/render-routing-metrics-trend.py", "--check")),
    LegacyCliCase("public-audit", ("scripts/audit-public-readiness.py",)),
    LegacyCliCase("markdown-links", ("scripts/check-markdown-links.py", ".")),
    LegacyCliCase(
        "release-smoke",
        ("scripts/smoke-release-assets.py", "--work-dir", "{tmp}/release-smoke"),
    ),
    LegacyCliCase("package-help", ("scripts/package-downloads.py", "--help")),
    LegacyCliCase(
        "package-env-root-refuses-missing-filters",
        ("scripts/package-downloads.py",),
        env={
            "WORKFLOW_SKILL_ROUTER_SKILLS_ROOT": "sample-skills",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES": "",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES": "",
            "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS": "",
        },
    ),
    LegacyCliCase(
        "package-refuses-unfiltered-private-root",
        ("scripts/package-downloads.py", "--skills-root", "sample-skills"),
        env={
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES": "",
            "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES": "",
            "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS": "",
        },
    ),
)
```

```python
# packages/router-core/tests/compat/test_legacy_cli_goldens.py
from __future__ import annotations

import json
from pathlib import Path
import unittest

from legacy_cli_cases import CASES
from golden_runner import run_case


GOLDEN = Path(__file__).with_name("golden") / "legacy-cli-v1.json"


class LegacyCliGoldenTests(unittest.TestCase):
    def test_every_declared_cli_matches_frozen_contract(self) -> None:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        actual = {case.name: run_case(case) for case in CASES}
        self.assertEqual(expected, actual)

    def test_case_names_are_unique_and_sorted_in_golden(self) -> None:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(len(CASES), len({case.name for case in CASES}))
        self.assertEqual(list(expected), sorted(expected))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the comparison and verify the harness fails before a golden exists**

Run: `python -m unittest discover -s packages/router-core/tests/compat -p "test_legacy_cli_goldens.py" -v`

Expected: FAIL with `FileNotFoundError: legacy-cli-v1.json`。任何 legacy script 的錯誤都不得在這一步被修改或忽略。

- [ ] **Step 3: Implement the deterministic subprocess runner and explicit capture command**

```python
# packages/router-core/tests/compat/golden_runner.py
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

from legacy_cli_cases import LegacyCliCase


REPO_ROOT = Path(__file__).resolve().parents[4]
CONTROLLED_ENV = (
    "WORKFLOW_SKILL_ROUTER_SKILLS_ROOT",
    "WORKFLOW_SKILL_ROUTER_EXCLUDE_NAMES",
    "WORKFLOW_SKILL_ROUTER_EXCLUDE_PREFIXES",
    "WORKFLOW_SKILL_ROUTER_PRIVATE_MARKERS",
    "WORKFLOW_SKILL_ROUTER_PUBLIC_FORBIDDEN_MARKERS",
)


def _normalize_text(value: str, tmp: Path) -> str:
    return (
        value.replace("\r\n", "\n")
        .replace(str(REPO_ROOT), "{repo}")
        .replace(REPO_ROOT.as_posix(), "{repo}")
        .replace(str(tmp), "{tmp}")
        .replace(tmp.as_posix(), "{tmp}")
    )


def _artifact(path: Path, tmp: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    result: dict[str, Any] = {
        "path": path.relative_to(tmp).as_posix(),
        "size": len(raw),
    }
    if path.suffix in {".json", ".jsonl", ".md", ".txt"}:
        text = _normalize_text(raw.decode("utf-8"), tmp)
        result["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        result["text"] = text
        if path.suffix == ".json":
            document = json.loads(text)
            result["json_top_level"] = type(document).__name__
            result["json_keys"] = sorted(document) if isinstance(document, dict) else []
    else:
        result["sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def run_case(case: LegacyCliCase) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="router-v1-golden-") as raw_tmp:
        tmp = Path(raw_tmp)
        for relative, content in sorted(case.input_files.items()):
            destination = tmp / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        argv = [part.replace("{tmp}", str(tmp)) for part in case.argv]
        env = os.environ.copy()
        for name in CONTROLLED_ENV:
            env.pop(name, None)
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **case.env})
        completed = subprocess.run(
            [sys.executable, *argv], cwd=REPO_ROOT, env=env,
            text=True, encoding="utf-8", errors="strict", capture_output=True, check=False,
        )
        return {
            "argv": list(case.argv),
            "env_overrides": {name: case.env[name] for name in sorted(case.env)},
            "exit_code": completed.returncode,
            "stdout": _normalize_text(completed.stdout, tmp),
            "stderr": _normalize_text(completed.stderr, tmp),
            "artifacts": [_artifact(tmp / name, tmp) for name in case.artifact_paths],
        }
```

```python
# packages/router-core/tests/compat/capture_legacy_cli_goldens.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legacy_cli_cases import CASES
from golden_runner import run_case


OUTPUT = Path(__file__).with_name("golden") / "legacy-cli-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="擷取目前 V1 CLI subprocess 契約。")
    parser.add_argument("--write", action="store_true", help="明確覆寫經人工審查的 golden。")
    args = parser.parse_args()
    if not args.write:
        parser.error("必須明確提供 --write")
    document = {case.name: run_case(case) for case in sorted(CASES, key=lambda item: item.name)}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create empty marker: `packages/router-core/tests/compat/__init__.py`。

- [ ] **Step 4: Capture twice, review the contract, and prove determinism**

Run: `python packages/router-core/tests/compat/capture_legacy_cli_goldens.py --write`

Expected: PASS with `Wrote ...legacy-cli-v1.json`，JSON 包含所有 case 的完整 stdout、stderr、exit code 與宣告 artifact。

Run: `python -m unittest discover -s packages/router-core/tests/compat -p "test_legacy_cli_goldens.py" -v`

Expected: 2 tests PASS。再執行同一測試一次仍 PASS。Golden runner 只正規化換行、repo root 與 temporary root；不得以廣泛 regex 遮蔽 timestamp 或其他內容漂移。具有 `--generated-at` 的 legacy producer必須使用 `FIXED_GENERATED_AT`；其他 producer 若產生非決定時間，應新增該 producer 已存在的固定時間輸入或把真實漂移保留在 golden review，不得刪掉輸出欄位。

- [ ] **Step 5: Commit the compatibility baseline**

```bash
git add packages/router-core/tests/compat
git commit -m "test(compat): freeze legacy cli contracts"
```

### Task 2: Establish the single distribution and versioned schema registry

**Files:**
- Create: `packages/router-core/pyproject.toml`
- Create: `packages/router-core/src/workflow_skill_router/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/artifacts.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/errors.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/registry.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/artifact-envelope.schema.json`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/capability.schema.json`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/capability-snapshot.schema.json`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/capability-drift.schema.json`
- Create: `packages/router-core/tests/schemas/test_registry.py`
- Create: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- Consumes: 無 V2 dependency；legacy scripts 保持隔離。
- Produces: `ArtifactEnvelope.from_dict(document) -> ArtifactEnvelope`、`ArtifactEnvelope.to_dict() -> dict[str, object]`、`canonical_json(document) -> str`、`canonical_json_bytes(document) -> bytes`、`SchemaRegistry.register(schema_id, schema_version, artifact_kind, decoder) -> None`、`SchemaRegistry.decode(document) -> object`。Registry key 固定是 `(schema_id, schema_version, artifact_kind)`。

- [ ] **Step 1: Write failing tests for triple-key dispatch, duplicate registration, UTF-8, and canonical output**

```python
# packages/router-core/tests/schemas/test_registry.py
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.schemas.artifacts import ArtifactEnvelope, canonical_json
from workflow_skill_router.schemas.errors import SchemaRegistryError
from workflow_skill_router.schemas.registry import SchemaRegistry


class SchemaRegistryTests(unittest.TestCase):
    def test_dispatch_requires_schema_id_version_and_kind(self) -> None:
        registry = SchemaRegistry()
        registry.register("workflow-skill-router/capability", "2.0.0-alpha.1", "capability", dict)
        document = {
            "schema_id": "workflow-skill-router/capability",
            "schema_version": "2.0.0-alpha.1",
            "artifact_kind": "capability",
            "artifact_id": "skill:sample/demo",
            "created_at": "2026-07-15T00:00:00Z",
            "payload": {"display_name": "繁體中文能力"},
        }
        self.assertEqual(document, registry.decode(document))
        document["artifact_kind"] = "capability-snapshot"
        with self.assertRaisesRegex(SchemaRegistryError, "未登錄的 schema contract"):
            registry.decode(document)

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = SchemaRegistry()
        registry.register("x", "2", "kind", dict)
        with self.assertRaisesRegex(SchemaRegistryError, "重複登錄"):
            registry.register("x", "2", "kind", dict)

    def test_envelope_canonical_json_preserves_utf8(self) -> None:
        envelope = ArtifactEnvelope.from_dict({
            "schema_id": "x", "schema_version": "2", "artifact_kind": "kind",
            "artifact_id": "id", "created_at": "2026-07-15T00:00:00Z",
            "payload": {"說明": "能力"},
        })
        self.assertIn("能力", canonical_json(envelope.to_dict()))
        self.assertNotIn("\\u80fd", canonical_json(envelope.to_dict()))
```

- [ ] **Step 2: Run tests and verify imports fail**

Run: `python -m unittest discover -s packages/router-core/tests/schemas -p "test_*.py" -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'workflow_skill_router'`。

- [ ] **Step 3: Implement package metadata, envelope, errors, and registry**

```toml
# packages/router-core/pyproject.toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "workflow-skill-router-core"
version = "2.0.0a1"
description = "Workflow Skill Router V2 deterministic core"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
workflow_skill_router = ["schemas/json/**/*.json", "persistence/migrations/*.sql"]
```

```python
# packages/router-core/src/workflow_skill_router/schemas/artifacts.py
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


def canonical_json(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return canonical_json(document).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ArtifactEnvelope:
    schema_id: str
    schema_version: str
    artifact_kind: str
    artifact_id: str
    created_at: str
    payload: Mapping[str, Any]

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "ArtifactEnvelope":
        required = ("schema_id", "schema_version", "artifact_kind", "artifact_id", "created_at", "payload")
        missing = [name for name in required if name not in document]
        if missing:
            raise ValueError(f"ArtifactEnvelope 缺少欄位: {', '.join(missing)}")
        payload = document["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("ArtifactEnvelope.payload 必須是 object")
        return cls(*(str(document[name]) for name in required[:-1]), payload=dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind, "artifact_id": self.artifact_id,
            "created_at": self.created_at, "payload": dict(self.payload),
        }
```

```python
# packages/router-core/src/workflow_skill_router/schemas/errors.py
class SchemaRegistryError(ValueError):
    """表示 artifact contract 無法安全分派。"""
```

```python
# packages/router-core/src/workflow_skill_router/schemas/registry.py
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeAlias

from .errors import SchemaRegistryError

SchemaKey: TypeAlias = tuple[str, str, str]
Decoder: TypeAlias = Callable[[Mapping[str, Any]], object]


class SchemaRegistry:
    def __init__(self) -> None:
        self._decoders: dict[SchemaKey, Decoder] = {}

    def register(self, schema_id: str, schema_version: str, artifact_kind: str, decoder: Decoder) -> None:
        key = (schema_id, schema_version, artifact_kind)
        if key in self._decoders:
            raise SchemaRegistryError(f"重複登錄 schema contract: {key}")
        self._decoders[key] = decoder

    def decode(self, document: Mapping[str, Any]) -> object:
        try:
            key = tuple(str(document[name]) for name in ("schema_id", "schema_version", "artifact_kind"))
        except KeyError as error:
            raise SchemaRegistryError(f"缺少 schema discriminator: {error.args[0]}") from error
        decoder = self._decoders.get(key)  # type: ignore[arg-type]
        if decoder is None:
            raise SchemaRegistryError(f"未登錄的 schema contract: {key}")
        return decoder(document)
```

Set `packages/router-core/src/workflow_skill_router/__init__.py` to `__version__ = "2.0.0a1"`，並在兩個 package `__init__.py` export 上述 public names。四份 JSON Schema 都使用 draft 2020-12、UTF-8、`additionalProperties: false`，其中 envelope `required` 必須完整列出六個 discriminator／payload 欄位；capability、snapshot 與 drift 的 required 欄位以本計畫 frozen DTO 為準，完整包含 `installer_content_digest`、固定 R0–R3 的 `availability_by_risk`，以及 drift 的 before/after snapshot identity；不得只複製較早設計章節後遺漏實作必填欄位。

- [ ] **Step 4: Add a schema-document test that rejects accidental discriminator drift**

```python
# packages/router-core/tests/schemas/test_schema_documents.py
import json
from pathlib import Path
import unittest


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "src/workflow_skill_router/schemas/json/v2"


class SchemaDocumentTests(unittest.TestCase):
    def test_all_documents_are_utf8_draft_2020_12_with_unique_ids(self) -> None:
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(SCHEMA_ROOT.glob("*.json"))]
        self.assertEqual(4, len(documents))
        self.assertEqual(4, len({item["$id"] for item in documents}))
        self.assertTrue(all(item["$schema"] == "https://json-schema.org/draft/2020-12/schema" for item in documents))

    def test_snapshot_schema_requires_immutable_identity_fields(self) -> None:
        document = json.loads((SCHEMA_ROOT / "capability-snapshot.schema.json").read_text(encoding="utf-8"))
        self.assertTrue({"snapshot_id", "schema_version", "created_at", "runtime_fingerprint", "provider_revisions", "capabilities", "freshness"}.issubset(document["required"]))

    def test_capability_schema_matches_content_and_risk_availability_model(self) -> None:
        document = json.loads((SCHEMA_ROOT / "capability.schema.json").read_text(encoding="utf-8"))
        self.assertTrue({"installer_content_digest", "availability_by_risk"}.issubset(document["required"]))
        availability = document["properties"]["availability_by_risk"]
        self.assertEqual(4, availability["minItems"])
        self.assertEqual(4, availability["maxItems"])
        self.assertEqual(["R0", "R1", "R2", "R3"], availability["x-risk-order"])

    def test_drift_schema_freezes_snapshot_and_change_identity(self) -> None:
        document = json.loads((SCHEMA_ROOT / "capability-drift.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(False, document["additionalProperties"])
        self.assertTrue({
            "drift_id", "previous_snapshot_id", "current_snapshot_id", "capability_id",
            "kind", "changed_fields", "before_fingerprint", "after_fingerprint", "detected_at",
        }.issubset(document["required"]))
```

- [ ] **Step 5: Run schema tests and commit**

Run: `python -m unittest discover -s packages/router-core/tests/schemas -p "test_*.py" -v`

Expected: all schema tests PASS，沒有第三方 import。

```bash
git add packages/router-core/pyproject.toml packages/router-core/src/workflow_skill_router packages/router-core/tests/schemas
git commit -m "feat(core): add v2 schema registry"
```

### Task 3: Model capability state and deterministic availability

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/capabilities/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/models.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/availability.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/codecs.py`
- Create: `packages/router-core/tests/capabilities/test_availability.py`
- Create: `packages/router-core/tests/capabilities/test_codecs.py`

**Interfaces:**
- Consumes: `canonical_json()` from Task 2。
- Produces: frozen enums／dataclasses `CapabilityKind`、`Presence`、`Exposure`、`AuthState`、`Eligibility`、`Compatibility`、`TrustLevel`、`RiskLevel`、`Availability`、`FieldObservation[T]`、`Freshness`、`Requirement`、`RiskAvailability`、`ProvenanceRecord`、`Capability`、`CapabilitySnapshot`；strict recursive `encode_capability/decode_capability`、`encode_snapshot/decode_snapshot`；package-owned `CAPABILITY_SCHEMA_REGISTRY` with capability/snapshot registrations；`derive_availability(capability, risk, now) -> AvailabilityResult`。Every nested value that contributes to snapshot identity is immutable；arbitrary mappings/lists are not stored in frozen DTOs。每個 snapshot capability 必須 materialize R0–R3 四筆非空結果，不能只保存 discovery request 當下的一個 risk。

- [ ] **Step 1: Write precedence tests before defining the models**

```python
# packages/router-core/tests/capabilities/test_availability.py
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.availability import derive_availability
from workflow_skill_router.capabilities.models import *


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def observed(value):
    return FieldObservation(value, "agent-runtime", NOW, TrustLevel.RUNTIME, "observed")


def capability(**changes):
    values = dict(
        canonical_id="skill:local/demo", display_name="Demo", kind=CapabilityKind.SKILL,
        source="local", presence=observed(Presence.PRESENT), exposure=observed(Exposure.EXPOSED),
        auth_state=observed(AuthState.NOT_REQUIRED), eligibility=observed(Eligibility.ELIGIBLE),
        compatibility=observed(Compatibility.COMPATIBLE),
        freshness=Freshness(NOW, NOW + timedelta(minutes=5), False), description="",
        domains=(), stages=(), side_effect=SideEffect.NONE, requirements=(), aliases=(),
        conflicts=(), context_cost=1, capability_fingerprint="abc",
        installer_content_digest=observed("unknown"), availability_by_risk=(), provenance=(),
    )
    values.update(changes)
    return Capability(**values)


class AvailabilityTests(unittest.TestCase):
    def test_incompatible_wins_over_absent_and_auth_required(self) -> None:
        item = capability(
            presence=observed(Presence.ABSENT), auth_state=observed(AuthState.REQUIRED),
            compatibility=observed(Compatibility.INCOMPATIBLE),
        )
        result = derive_availability(item, RiskLevel.R1, NOW)
        self.assertEqual(Availability.INCOMPATIBLE, result.primary)
        self.assertEqual(("compatibility-incompatible", "presence-absent", "auth-required"), result.reasons)

    def test_unknown_authoritative_field_is_not_available(self) -> None:
        item = capability(exposure=observed(Exposure.UNKNOWN))
        self.assertEqual(Availability.UNKNOWN, derive_availability(item, RiskLevel.R0, NOW).primary)

    def test_r2_rejects_expired_freshness_while_r0_can_be_degraded(self) -> None:
        item = capability(freshness=Freshness(NOW - timedelta(hours=1), NOW - timedelta(minutes=1), True))
        self.assertEqual(Availability.DEGRADED, derive_availability(item, RiskLevel.R0, NOW).primary)
        self.assertEqual(Availability.STALE, derive_availability(item, RiskLevel.R2, NOW).primary)
```

- [ ] **Step 2: Run tests and verify missing capability modules**

Run: `python -m unittest packages/router-core/tests/capabilities/test_availability.py packages/router-core/tests/capabilities/test_codecs.py -v`

Expected: FAIL with `ModuleNotFoundError` for `workflow_skill_router.capabilities`。

- [ ] **Step 3: Implement immutable contracts and precedence**

```python
# packages/router-core/src/workflow_skill_router/capabilities/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, Mapping, TypeVar


class CapabilityKind(StrEnum): SKILL="skill"; MCP_TOOL="mcp-tool"; PLUGIN="plugin"; APP="app"; HOST_TOOL="host-tool"
class Presence(StrEnum): PRESENT="present"; ABSENT="absent"; NOT_APPLICABLE="not-applicable"; UNKNOWN="unknown"
class Exposure(StrEnum): EXPOSED="exposed"; NOT_EXPOSED="not-exposed"; UNKNOWN="unknown"
class AuthState(StrEnum): AUTHORIZED="authorized"; REQUIRED="required"; NOT_REQUIRED="not-required"; UNKNOWN="unknown"
class Eligibility(StrEnum): ELIGIBLE="eligible"; INELIGIBLE="ineligible"; UNKNOWN="unknown"
class Compatibility(StrEnum): COMPATIBLE="compatible"; INCOMPATIBLE="incompatible"; UNKNOWN="unknown"
class TrustLevel(StrEnum): CACHE="cache"; METADATA="metadata"; HANDSHAKE="handshake"; RUNTIME="runtime"
class RiskLevel(StrEnum): R0="R0"; R1="R1"; R2="R2"; R3="R3"
class Availability(StrEnum): AVAILABLE="available"; UNAVAILABLE="unavailable"; AUTH_REQUIRED="auth-required"; DEGRADED="degraded"; STALE="stale"; UNKNOWN="unknown"; INCOMPATIBLE="incompatible"
class SideEffect(StrEnum): NONE="none"; LOCAL="local"; REMOTE="remote"; PRIVILEGED="privileged"
class DriftKind(StrEnum):
    ADD="add"; REMOVE="remove"; RENAME="rename"; SEMANTIC_METADATA="semantic-metadata"
    INSTRUCTION_CONTENT="instruction-content"; TOOL_SCHEMA="tool-schema"; AUTH="auth"
    POLICY="policy"; RUNTIME_EXPOSURE="runtime-exposure"

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class FieldObservation(Generic[T]):
    value: T; provider: str; observed_at: datetime; trust_level: TrustLevel; reason_code: str

@dataclass(frozen=True, slots=True)
class Freshness:
    observed_at: datetime; expires_at: datetime; degraded_allowed: bool; stale: bool = False

@dataclass(frozen=True, slots=True)
class Requirement:
    canonical_id: str; kind: CapabilityKind; purpose: str; trusted: bool

@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    primary: Availability; reasons: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class RiskAvailability:
    risk: RiskLevel; result: AvailabilityResult

@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    provider_id: str; source_kind: str; source_ref_digest: str
    observation_digest: str; trust_level: TrustLevel; reason_code: str

@dataclass(frozen=True, slots=True)
class Capability:
    canonical_id: str; display_name: str; kind: CapabilityKind; source: str
    presence: FieldObservation[Presence]; exposure: FieldObservation[Exposure]
    auth_state: FieldObservation[AuthState]; eligibility: FieldObservation[Eligibility]
    compatibility: FieldObservation[Compatibility]; freshness: Freshness; description: str
    domains: tuple[str, ...]; stages: tuple[str, ...]; side_effect: SideEffect
    requirements: tuple[Requirement, ...]; aliases: tuple[str, ...]; conflicts: tuple[str, ...]
    context_cost: int; capability_fingerprint: str
    installer_content_digest: FieldObservation[str]
    availability_by_risk: tuple[RiskAvailability, ...]
    provenance: tuple[ProvenanceRecord, ...]

@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    snapshot_id: str; schema_version: str; created_at: str; runtime_fingerprint: str
    provider_revisions: tuple[str, ...]; capabilities: tuple[Capability, ...]
    drift_from_snapshot_id: str | None; freshness: Freshness

@dataclass(frozen=True, slots=True)
class CapabilityDrift:
    drift_id: str; previous_snapshot_id: str | None; current_snapshot_id: str
    capability_id: str; kind: DriftKind; changed_fields: tuple[str, ...]
    before_fingerprint: str | None; after_fingerprint: str | None; detected_at: str
```

`codecs.py` must enumerate every allowed key at every nesting level and parse enums/timestamps explicitly；it cannot use a permissive `dict` decoder or silently drop unknown keys。The capability schema defines each provenance item with the six exact `ProvenanceRecord` fields and `additionalProperties:false`。`encode_capability()` and `encode_snapshot()` wrap payloads in the Task 2 `ArtifactEnvelope` with schema IDs `workflow-skill-router/capability` and `workflow-skill-router/capability-snapshot`。`capabilities/__init__.py` creates one `CAPABILITY_SCHEMA_REGISTRY`, registers both strict decoders exactly once, and Task 5 extends the same registry with drift—not a parallel registry。Plan 03 `SnapshotReader` and cache provider decode persisted snapshots only through this registry。

```python
# packages/router-core/tests/capabilities/test_codecs.py
class CapabilityCodecTests(unittest.TestCase):
    def test_nested_snapshot_round_trips_through_default_registry(self) -> None:
        envelope = encode_snapshot(SNAPSHOT_WITH_TRADITIONAL_CHINESE_METADATA)
        decoded = CAPABILITY_SCHEMA_REGISTRY.decode(envelope.to_dict())
        self.assertEqual(SNAPSHOT_WITH_TRADITIONAL_CHINESE_METADATA, decoded)

    def test_unknown_nested_capability_field_is_rejected(self) -> None:
        document = encode_snapshot(SNAPSHOT).to_dict()
        document["payload"]["capabilities"][0]["client_trusted"] = True
        with self.assertRaisesRegex(SchemaRegistryError, "unknown field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)

    def test_missing_nested_freshness_field_is_rejected(self) -> None:
        document = encode_capability(CAPABILITY).to_dict()
        del document["payload"]["freshness"]["expires_at"]
        with self.assertRaisesRegex(SchemaRegistryError, "missing field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)
```

```python
# packages/router-core/src/workflow_skill_router/capabilities/availability.py
from __future__ import annotations

from datetime import datetime

from .models import *


def derive_availability(capability: Capability, risk: RiskLevel, now: datetime) -> AvailabilityResult:
    reasons: list[str] = []
    if capability.compatibility.value is Compatibility.INCOMPATIBLE: reasons.append("compatibility-incompatible")
    if capability.presence.value is Presence.ABSENT: reasons.append("presence-absent")
    if capability.exposure.value is Exposure.NOT_EXPOSED: reasons.append("exposure-not-exposed")
    if capability.eligibility.value is Eligibility.INELIGIBLE: reasons.append("policy-ineligible")
    if capability.auth_state.value is AuthState.REQUIRED: reasons.append("auth-required")
    unknown = (
        capability.presence.value is Presence.UNKNOWN or capability.exposure.value is Exposure.UNKNOWN
        or capability.auth_state.value is AuthState.UNKNOWN or capability.eligibility.value is Eligibility.UNKNOWN
        or capability.compatibility.value is Compatibility.UNKNOWN
    )
    stale = now > capability.freshness.expires_at
    degraded = any(field.trust_level is TrustLevel.CACHE for field in (
        capability.presence, capability.exposure, capability.auth_state,
        capability.eligibility, capability.compatibility,
    ))
    if reasons and reasons[0] == "compatibility-incompatible": primary = Availability.INCOMPATIBLE
    elif any(reason in reasons for reason in ("presence-absent", "exposure-not-exposed", "policy-ineligible")): primary = Availability.UNAVAILABLE
    elif "auth-required" in reasons: primary = Availability.AUTH_REQUIRED
    elif unknown: primary = Availability.UNKNOWN
    elif stale and (risk in (RiskLevel.R2, RiskLevel.R3) or not capability.freshness.degraded_allowed): primary = Availability.STALE
    elif stale or degraded: primary = Availability.DEGRADED
    else: primary = Availability.AVAILABLE
    return AvailabilityResult(primary, tuple(reasons))
```

- [ ] **Step 4: Run focused and schema tests, then commit**

Run: `python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v`

Expected: compatibility、schema、availability tests 全部 PASS。

```bash
git add packages/router-core/src/workflow_skill_router/capabilities packages/router-core/tests/capabilities
git commit -m "feat(core): model capability availability"
```

### Task 4: Build a frontmatter-only filesystem metadata provider

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/capabilities/frontmatter.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/filesystem.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/providers.py`
- Create: `packages/router-core/tests/capabilities/test_frontmatter.py`
- Create: `packages/router-core/tests/capabilities/test_filesystem_provider.py`

**Interfaces:**
- Consumes: `CapabilityKind`、`Presence` 與 field observation contracts from Task 3。
- Produces: `read_frontmatter_stream(stream: BinaryIO, max_bytes: int = 65536) -> bytes`、`parse_frontmatter(data: bytes) -> Mapping[str, object]`、`InstallerManifestIndex.lookup(skill_path) -> InstallerContentClaim | None`、`FilesystemMetadataProvider.discover(context: DiscoveryContext) -> ProviderResult`、`CapabilityObservation`、`ProviderResult`、`DiscoveryContext`、`CapabilityProvider` protocol。

- [ ] **Step 1: Write security tests proving the body is not read**

```python
# packages/router-core/tests/capabilities/test_frontmatter.py
from io import BytesIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.frontmatter import FrontmatterError, parse_frontmatter, read_frontmatter_stream


class GuardedReader(BytesIO):
    def readline(self, size=-1):
        if self.tell() >= self.getvalue().index(b"# instruction"):
            raise AssertionError("discovery 讀取了 instruction body")
        return super().readline(size)


class FrontmatterTests(unittest.TestCase):
    def test_reader_stops_at_closing_delimiter(self) -> None:
        stream = GuardedReader(b"---\nname: demo\ndescription: metadata only\n---\n# instruction\nnever read")
        self.assertEqual("demo", parse_frontmatter(read_frontmatter_stream(stream))["name"])

    def test_invalid_utf8_in_instruction_body_does_not_break_discovery(self) -> None:
        stream = BytesIO(b"---\nname: demo\ndescription: ok\n---\n\xff\xfe")
        self.assertEqual("demo", parse_frontmatter(read_frontmatter_stream(stream))["name"])

    def test_duplicate_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(FrontmatterError, "重複 key"):
            parse_frontmatter(b"name: one\nname: two\n")
```

- [ ] **Step 2: Run tests and verify the header-only reader is absent**

Run: `python -m unittest packages/router-core/tests/capabilities/test_frontmatter.py -v`

Expected: FAIL with `ModuleNotFoundError` for `capabilities.frontmatter`。

- [ ] **Step 3: Implement a bounded header reader and non-executing YAML subset**

```python
# packages/router-core/src/workflow_skill_router/capabilities/frontmatter.py
from __future__ import annotations

from typing import BinaryIO


class FrontmatterError(ValueError):
    """表示 SKILL metadata 不可信或格式無效。"""


def read_frontmatter_stream(stream: BinaryIO, max_bytes: int = 65536) -> bytes:
    first = stream.readline(max_bytes + 1)
    if first.rstrip(b"\r\n") != b"---":
        raise FrontmatterError("SKILL.md 缺少 frontmatter 起始符號")
    consumed = len(first)
    lines: list[bytes] = []
    while consumed <= max_bytes:
        line = stream.readline(max_bytes - consumed + 1)
        if not line:
            raise FrontmatterError("SKILL.md 缺少 frontmatter 結束符號")
        consumed += len(line)
        if consumed > max_bytes:
            raise FrontmatterError("frontmatter 超過 65536 bytes")
        if line.rstrip(b"\r\n") == b"---":
            return b"".join(lines)
        lines.append(line)
    raise FrontmatterError("frontmatter 超過 65536 bytes")


def parse_frontmatter(data: bytes) -> dict[str, object]:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise FrontmatterError("frontmatter 必須是有效 UTF-8") from error
    result: dict[str, object] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == "metadata:":
            if "metadata" in result:
                raise FrontmatterError("重複 key: metadata")
            result["metadata"] = metadata
            in_metadata = True
            continue
        if ":" not in raw:
            raise FrontmatterError(f"第 {number} 行不是 key: value")
        key, value = raw.split(":", 1)
        target = metadata if raw.startswith(("  ", "\t")) and in_metadata else result
        key = key.strip()
        if key in target:
            raise FrontmatterError(f"重複 key: {key}")
        target[key] = value.strip().strip('"').strip("'")
    if not isinstance(result.get("name"), str) or not result["name"]:
        raise FrontmatterError("frontmatter 缺少 name")
    return result
```

- [ ] **Step 4: Test and implement trusted-root, size, symlink, UTF-8, and identity behavior**

```python
# packages/router-core/tests/capabilities/test_filesystem_provider.py
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.filesystem import FilesystemMetadataProvider
from workflow_skill_router.capabilities.providers import DiscoveryContext


class FilesystemProviderTests(unittest.TestCase):
    def test_identity_is_source_qualified_and_body_is_excluded_from_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "demo" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text("---\nname: demo\ndescription: first\n---\n# instruction A\n", encoding="utf-8")
            provider = FilesystemMetadataProvider((Path(directory),))
            first = provider.discover(DiscoveryContext("runtime", "R0")).observations[0]
            skill.write_text("---\nname: demo\ndescription: first\n---\n# instruction B\n", encoding="utf-8")
            second = provider.discover(DiscoveryContext("runtime", "R0")).observations[0]
            self.assertEqual("skill:filesystem/demo", first.canonical_id)
            self.assertEqual(first.fields["capability_fingerprint"].value, second.fields["capability_fingerprint"].value)

    def test_discovery_preserves_trusted_installer_digest_without_opening_body(self) -> None:
        provider = provider_with_trusted_installer_claim("sha256:" + "a" * 64)
        observation = provider.discover(DiscoveryContext("runtime", "R1")).observations[0]
        self.assertEqual("sha256:" + "a" * 64, observation.fields["installer_content_digest"].value)
        self.assertEqual("trusted-installer-manifest", observation.fields["installer_content_digest"].reason_code)
```

Implement `providers.py` with frozen `DiscoveryContext(runtime_fingerprint: str, risk: str)`、`CapabilityObservation(canonical_id, kind, source, fields)`、`ProviderResult(provider_id, revision, observed_at, observations, degraded, reasons)` and `CapabilityProvider.discover(context) -> ProviderResult` protocol。Implement `filesystem.py` so it resolves each allowed root, rejects candidates whose `resolve()` is outside that root, skips symlink／junction directories, limits each frontmatter to 65,536 bytes, uses `read_frontmatter_stream()`, creates `skill:filesystem/<normalized-name>` IDs, and fingerprints canonical frontmatter metadata only。`InstallerManifestIndex` 由受信 installer adapter 注入、其 claim 必須含 installer identity／manifest digest／content digest；不得信任 `SKILL.md` 自己宣告的 digest。若沒有可信 claim，`installer_content_digest` 是顯式 `unknown` observation。Discovery 不可為了補 digest 開啟 closing delimiter 後的 body。`exposure`、`auth_state` remain `unknown`; filesystem presence alone must never produce `available`。

- [ ] **Step 5: Run filesystem tests and commit**

Run: `python -m unittest discover -s packages/router-core/tests/capabilities -p "test_*frontmatter*.py" -v`

Expected: all frontmatter tests PASS。

Run: `python -m unittest packages/router-core/tests/capabilities/test_filesystem_provider.py -v`

Expected: PASS；body-only change does not change metadata routing fingerprint，且可信 installer digest 只由 manifest observation 取得、不是由 Discovery 讀 body 計算。

```bash
git add packages/router-core/src/workflow_skill_router/capabilities packages/router-core/tests/capabilities
git commit -m "feat(core): discover skill metadata safely"
```

### Task 5: Merge providers into immutable snapshots and detect typed drift

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/capabilities/merge.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/snapshot.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/drift.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/discovery.py`
- Create: `packages/router-core/tests/capabilities/test_merge.py`
- Create: `packages/router-core/tests/capabilities/test_snapshot.py`
- Create: `packages/router-core/tests/capabilities/test_drift_codec.py`
- Create: `packages/router-core/tests/capabilities/test_discovery_performance.py`

**Interfaces:**
- Consumes: `CapabilityObservation`／`ProviderResult` from Task 4 and `Capability`／`CapabilitySnapshot` from Task 3。
- Produces: `merge_observations(results, risk, now) -> tuple[Capability, ...]`、`build_snapshot(results, runtime_fingerprint, previous, now) -> CapabilitySnapshot`、`compare_snapshots(previous, current) -> tuple[CapabilityDrift, ...]`、strict `encode_drift(drift) -> ArtifactEnvelope`／`decode_drift(envelope) -> CapabilityDrift`、`DiscoveryService.discover(context, previous=None) -> DiscoveryResult`。Drift kind 固定為 `add | remove | rename | semantic-metadata | instruction-content | tool-schema | auth | policy | runtime-exposure`；the exact frozen DTO is the Task 3 `CapabilityDrift` contract and its schema ID is `workflow-skill-router/capability-drift`。

- [ ] **Step 1: Write failing field-authority and cache non-promotion tests**

```python
# packages/router-core/tests/capabilities/test_merge.py
class ProviderMergeTests(unittest.TestCase):
    def test_host_exposure_wins_over_filesystem_and_cache(self) -> None:
        merged = merge_observations((filesystem_present(), cache_exposed(), host_not_exposed()), RiskLevel.R1, NOW)
        self.assertEqual(Exposure.NOT_EXPOSED, merged[0].exposure.value)
        self.assertEqual(Availability.UNAVAILABLE, derive_availability(merged[0], RiskLevel.R1, NOW).primary)

    def test_cache_cannot_promote_runtime_unavailable(self) -> None:
        merged = merge_observations((host_not_exposed(), cache_available()), RiskLevel.R1, NOW)
        self.assertEqual(Exposure.NOT_EXPOSED, merged[0].exposure.value)
        self.assertNotEqual(Availability.AVAILABLE, derive_availability(merged[0], RiskLevel.R1, NOW).primary)

    def test_same_display_name_from_two_sources_is_not_deduplicated(self) -> None:
        merged = merge_observations((filesystem_named_demo(), plugin_named_demo()), RiskLevel.R0, NOW)
        self.assertEqual(["skill:filesystem/demo", "skill:plugin/demo"], [item.canonical_id for item in merged])

    def test_every_capability_materializes_non_null_risk_availability(self) -> None:
        item = merge_observations((stale_filesystem_capability(),), RiskLevel.R0, NOW)[0]
        by_risk = {entry.risk: entry.result for entry in item.availability_by_risk}
        self.assertEqual(set(RiskLevel), set(by_risk))
        self.assertTrue(all(result.primary is not None and result.reasons is not None for result in by_risk.values()))
        self.assertNotEqual(by_risk[RiskLevel.R0].primary, by_risk[RiskLevel.R2].primary)
```

The fixture builders in this test must return real `ProviderResult`／`CapabilityObservation` objects with fixed timestamps and complete fields; do not mock `merge_observations()` itself。

- [ ] **Step 2: Run merge tests and verify missing implementation**

Run: `python -m unittest packages/router-core/tests/capabilities/test_merge.py -v`

Expected: FAIL with `ModuleNotFoundError: ...capabilities.merge`。

- [ ] **Step 3: Implement field authority and deterministic snapshot identity**

```python
# packages/router-core/src/workflow_skill_router/capabilities/merge.py
FIELD_AUTHORITY = {
    "presence": ("native-host", "plugin-handshake", "agent-runtime", "filesystem", "cache"),
    "exposure": ("native-host", "agent-runtime", "plugin-handshake", "cache", "filesystem"),
    "auth_state": ("native-host", "plugin-handshake", "agent-runtime", "cache", "filesystem"),
    "eligibility": ("native-host", "agent-runtime", "plugin-handshake", "filesystem", "cache"),
    "compatibility": ("plugin-handshake", "native-host", "agent-runtime", "filesystem", "cache"),
    "display_name": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "description": ("filesystem", "plugin-handshake", "agent-runtime", "native-host", "cache"),
    "capability_fingerprint": ("plugin-handshake", "filesystem", "native-host", "agent-runtime", "cache"),
    "installer_content_digest": ("native-host", "plugin-handshake", "filesystem", "agent-runtime", "cache"),
}


def _select(field: str, observations):
    order = FIELD_AUTHORITY[field]
    return min(observations, key=lambda item: (order.index(item.provider), -item.observed_at.timestamp()))


def merge_observations(results, risk, now):
    grouped = {}
    for result in results:
        for observation in result.observations:
            grouped.setdefault(observation.canonical_id, []).append(observation)
    return tuple(_materialize(canonical_id, grouped[canonical_id], risk, now) for canonical_id in sorted(grouped))
```

`_materialize()` must select each field independently, attach every losing observation to provenance, preserve aliases, never merge different canonical IDs by display name, and call `derive_availability()` only after all authoritative fields are selected。它先建立 `availability_by_risk=()` 的 provisional frozen `Capability`，再以 `dataclasses.replace()` 寫入依 `tuple(RiskLevel)` 固定順序產生的四筆 `RiskAvailability(risk, derive_availability(...))`；R0–R3 不得缺值或使用資料庫 `NULL`。Unknown fields use an explicit `unknown` observation rather than Python `None`。`installer_content_digest` 只接受可驗證 host／plugin handshake 或 trusted installer manifest observation；agent/cache 不得提升未知 digest 的可信度。

```python
# packages/router-core/src/workflow_skill_router/capabilities/snapshot.py
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib

from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from .models import CapabilitySnapshot, Freshness


SCHEMA_VERSION = "2.0.0-alpha.1"


def build_snapshot(results, runtime_fingerprint, previous, now=None):
    created = now or datetime.now(timezone.utc)
    capabilities = merge_observations(results, RiskLevel.R0, created)
    expires_at = min(
        (item.freshness.expires_at for item in capabilities),
        default=created,
    )
    freshness = Freshness(created, expires_at, False, not capabilities)
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "runtime_fingerprint": runtime_fingerprint,
        "provider_revisions": sorted(f"{item.provider_id}:{item.revision}" for item in results),
        "capabilities": [asdict(item) for item in capabilities],
        "drift_from_snapshot_id": previous.snapshot_id if previous else None,
        "freshness": asdict(freshness),
    }
    snapshot_id = "sha256:" + hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest()
    return CapabilitySnapshot(
        snapshot_id, SCHEMA_VERSION, created.isoformat().replace("+00:00", "Z"), runtime_fingerprint,
        tuple(identity_payload["provider_revisions"]), capabilities,
        previous.snapshot_id if previous else None,
        freshness,
    )
```

Before hashing, convert enums and datetimes to their string values with one recursive canonicalizer; the same logical observations in a different provider completion order must yield the same `snapshot_id`。

- [ ] **Step 4: Add drift, concurrency, and 1,000-capability acceptance tests**

```python
# packages/router-core/tests/capabilities/test_snapshot.py
class SnapshotTests(unittest.TestCase):
    def test_all_providers_failed_builds_typed_stale_empty_snapshot(self) -> None:
        snapshot = build_snapshot((), "runtime-a", None, NOW)
        self.assertEqual((), snapshot.capabilities)
        self.assertTrue(snapshot.freshness.stale)
        self.assertEqual(NOW, snapshot.freshness.expires_at)

    def test_provider_completion_order_does_not_change_snapshot_id(self) -> None:
        first = build_snapshot((HOST, FILESYSTEM), "runtime-a", None, NOW)
        second = build_snapshot((FILESYSTEM, HOST), "runtime-a", None, NOW)
        self.assertEqual(first.snapshot_id, second.snapshot_id)

    def test_snapshot_time_or_previous_identity_changes_snapshot_id(self) -> None:
        first = build_snapshot((HOST,), "runtime-a", None, NOW)
        later = build_snapshot((HOST,), "runtime-a", first, NOW + timedelta(seconds=1))
        self.assertNotEqual(first.snapshot_id, later.snapshot_id)

    def test_snapshot_is_frozen(self) -> None:
        snapshot = build_snapshot((HOST, FILESYSTEM), "runtime-a", None, NOW)
        with self.assertRaises(FrozenInstanceError):
            snapshot.runtime_fingerprint = "changed"

    def test_nested_provenance_is_frozen_and_snapshot_hash_cannot_drift(self) -> None:
        snapshot = build_snapshot((HOST,), "runtime-a", None, NOW)
        before = snapshot.snapshot_id
        with self.assertRaises(FrozenInstanceError):
            snapshot.capabilities[0].provenance[0].provider_id = "forged"
        self.assertEqual(before, snapshot.snapshot_id)
        self.assertEqual(before, rebuild_snapshot_id(snapshot))

    def test_semantic_fingerprint_change_is_typed_drift(self) -> None:
        before = build_snapshot((provider(fingerprint="one"),), "runtime-a", None, NOW)
        after = build_snapshot((provider(fingerprint="two"),), "runtime-a", before, NOW)
        self.assertEqual((DriftKind.SEMANTIC_METADATA,), tuple(item.kind for item in compare_snapshots(before, after)))

    def test_trusted_installer_content_digest_change_is_typed_drift(self) -> None:
        before = build_snapshot((provider(installer_content_digest="sha256:" + "1" * 64),), "runtime-a", None, NOW)
        after = build_snapshot((provider(installer_content_digest="sha256:" + "2" * 64),), "runtime-a", before, NOW)
        self.assertEqual((DriftKind.INSTRUCTION_CONTENT,), tuple(item.kind for item in compare_snapshots(before, after)))
```

```python
# packages/router-core/tests/capabilities/test_drift_codec.py
class CapabilityDriftCodecTests(unittest.TestCase):
    def test_drift_round_trips_through_registered_versioned_envelope(self) -> None:
        drift = CapabilityDrift(
            drift_id="sha256:" + "d" * 64,
            previous_snapshot_id="sha256:" + "1" * 64,
            current_snapshot_id="sha256:" + "2" * 64,
            capability_id="skill:filesystem/demo",
            kind=DriftKind.INSTRUCTION_CONTENT,
            changed_fields=("installer_content_digest",),
            before_fingerprint="sha256:" + "3" * 64,
            after_fingerprint="sha256:" + "4" * 64,
            detected_at="2026-07-15T00:00:00Z",
        )
        envelope = encode_drift(drift)
        self.assertEqual("workflow-skill-router/capability-drift", envelope.schema_id)
        self.assertEqual(drift, CAPABILITY_SCHEMA_REGISTRY.decode(envelope.to_dict()))

    def test_drift_decoder_rejects_unknown_or_missing_fields(self) -> None:
        document = encode_drift(DRIFT).to_dict()
        document["payload"]["runtime_fingerprint"] = "client-forged"
        with self.assertRaisesRegex(SchemaRegistryError, "unknown field"):
            CAPABILITY_SCHEMA_REGISTRY.decode(document)
```

```python
# packages/router-core/tests/capabilities/test_discovery_performance.py
class DiscoveryPerformanceTests(unittest.TestCase):
    def test_warm_discovery_of_one_thousand_capabilities_is_under_two_seconds(self) -> None:
        service = DiscoveryService((StaticProvider.with_count(1000),))
        start = time.perf_counter()
        result = service.discover(DiscoveryContext("runtime-a", "R1"))
        elapsed = time.perf_counter() - start
        self.assertEqual(1000, len(result.snapshot.capabilities))
        self.assertLess(elapsed, 2.0)
```

Task 5 registers the strict drift decoder into `CAPABILITY_SCHEMA_REGISTRY` and duplicate registration is an error。`DiscoveryService` uses bounded concurrent provider calls、provider-specific timeout、deterministic result ordering, and returns `DiscoveryResult(snapshot, drift, provider_failures, used_degraded_provider)`。A provider timeout remains an explicit degraded failure；it cannot be silently omitted。`used_degraded_provider` is true when a contributing degraded observation affects the snapshot。When every provider fails and no cache exists, `build_snapshot()` returns a typed empty snapshot with `expires_at=created_at` and `stale=True`；the service returns every failure and `degraded=True` instead of calling `min()` on an empty collection or inventing availability。`compare_snapshots()` compares canonical IDs first, then aliases／frontmatter fingerprint／trusted `installer_content_digest`／tool schema／auth／policy／exposure and returns stable-sorted typed records；each record derives `drift_id` from the canonical payload excluding `drift_id` itself, and before/after fingerprint is explicit even for add/remove。Content digest changes emit `DriftKind.INSTRUCTION_CONTENT`；Plan 03 persists the full strict envelope as a content-addressed artifact and appends an exact server-owned `CAPABILITY_DRIFT_DETECTED` identity/ref payload even when frontmatter is unchanged。Replay opens the verified artifact and decodes it through the same registry rather than accepting an untyped mapping。

- [ ] **Step 5: Run the complete foundation suite and commit**

Run: `python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v`

Expected: all V1 golden、schema、security、merge、snapshot、drift tests PASS；performance test reports `< 2.0s`。

Run: `python -m compileall -q packages/router-core/src packages/router-core/tests`

Expected: exit 0 and no output。

```bash
git add packages/router-core/src/workflow_skill_router/capabilities packages/router-core/tests/capabilities
git commit -m "feat(core): build immutable capability discovery"
```

### Task 6: Implement concrete runtime providers and verified context sync

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/capabilities/native_host.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/plugin_handshake.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/agent_runtime.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/cache.py`
- Create: `packages/router-core/src/workflow_skill_router/capabilities/runtime_context.py`
- Create: `packages/router-core/tests/capabilities/test_runtime_providers.py`
- Create: `packages/router-core/tests/capabilities/test_runtime_context.py`

**Interfaces:**
- Consumes: `CapabilityProvider`、`ProviderResult`、`DiscoveryService`、`CapabilitySnapshot` and `CapabilityDrift` from Tasks 3–5；host and handshake values arrive only through injected verifier ports。
- Produces: `NativeHostProvider`、`PluginHandshakeProvider`、`AgentRuntimeSnapshotProvider`、`CachedSnapshotProvider`；`RuntimeContextSyncRequest`；`ProviderFailure(provider_id, reason_code, timed_out, degraded)`；`SyncRuntimeContextResult(snapshot, drift, provider_failures, cache_used, degraded)`；`RuntimeContextService.sync_verified(request: RuntimeContextSyncRequest) -> SyncRuntimeContextResult`。

- [ ] **Step 1: Write failing concrete-provider, handshake, cache, and timeout tests**

```python
# packages/router-core/tests/capabilities/test_runtime_providers.py
class RuntimeProviderTests(unittest.TestCase):
    def test_host_not_exposed_beats_agent_and_cache_available(self) -> None:
        providers = (
            NativeHostProvider.from_verified(verified_host(exposure="not-exposed")),
            AgentRuntimeSnapshotProvider(agent_snapshot(exposure="exposed")),
            CachedSnapshotProvider(previous_available_snapshot()),
        )
        result = DiscoveryService(providers).discover(DiscoveryContext("runtime-a", "R1"))
        capability = result.snapshot.capabilities[0]
        self.assertEqual(Exposure.NOT_EXPOSED, capability.exposure.value)
        self.assertNotEqual(Availability.AVAILABLE, derive_availability(capability, RiskLevel.R1, NOW).primary)

    def test_plugin_handshake_fingerprints_schema_and_preserves_auth_required(self) -> None:
        provider = PluginHandshakeProvider.from_verified(verified_handshake(
            tool_name="validate_route", schema={"type": "object", "required": ["route"]},
            healthy=True, auth_state="required",
        ))
        observation = provider.discover(DiscoveryContext("runtime-a", "R1")).observations[0]
        self.assertEqual("mcp-tool:workflow-skill-router/validate_route", observation.canonical_id)
        self.assertEqual("required", observation.fields["auth_state"].value)
        self.assertTrue(observation.fields["capability_fingerprint"].value.startswith("sha256:"))

    def test_agent_snapshot_never_claims_host_authorization(self) -> None:
        observation = AgentRuntimeSnapshotProvider(
            agent_snapshot(exposure="exposed", requested_auth_state="authorized")
        ).discover(DiscoveryContext("runtime-a", "R1")).observations[0]
        self.assertEqual("unknown", observation.fields["auth_state"].value)
        self.assertEqual(TrustLevel.RUNTIME, observation.fields["exposure"].trust_level)
```

```python
# packages/router-core/tests/capabilities/test_runtime_context.py
class RuntimeContextServiceTests(unittest.TestCase):
    def test_forged_host_payload_without_verified_reference_is_rejected(self) -> None:
        request = runtime_request(host_snapshot_ref="unregistered-host-receipt")
        with self.assertRaisesRegex(RuntimeContextVerificationError, "host_receipt_unverified"):
            self.service.sync_verified(request)

    def test_provider_timeout_is_returned_and_snapshot_is_degraded(self) -> None:
        service = runtime_service(
            handshake_verifier=BlockingHandshakeVerifier(),
            provider_deadlines={"plugin-handshake": 0.01},
        )
        result = service.sync_verified(runtime_request(plugin_handshake_ref="hs-1"))
        self.assertTrue(result.degraded)
        self.assertEqual(("plugin-handshake",), tuple(item.provider_id for item in result.provider_failures))
        self.assertTrue(result.provider_failures[0].timed_out)

    def test_cache_is_reported_but_cannot_promote_runtime_unavailable(self) -> None:
        result = self.service.sync_verified(runtime_request(
            verified_host=verified_host(exposure="not-exposed"), previous=previous_available_snapshot()
        ))
        self.assertTrue(result.cache_used)
        availability = derive_availability(result.snapshot.capabilities[0], RiskLevel.R1, NOW)
        self.assertNotEqual(Availability.AVAILABLE, availability.primary)
```

- [ ] **Step 2: Run the focused tests and verify concrete adapters are absent**

Run: `python -m unittest packages/router-core/tests/capabilities/test_runtime_providers.py packages/router-core/tests/capabilities/test_runtime_context.py -v`

Expected: FAIL with missing `native_host`、`plugin_handshake`、`agent_runtime`、`cache` and `runtime_context` modules。

- [ ] **Step 3: Implement verified provider DTOs and field-authority limits**

```python
# packages/router-core/src/workflow_skill_router/capabilities/runtime_context.py
from __future__ import annotations

from dataclasses import dataclass

from .drift import CapabilityDrift
from .models import CapabilitySnapshot, RiskLevel


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider_id: str
    reason_code: str
    timed_out: bool
    degraded: bool


@dataclass(frozen=True, slots=True)
class AgentCapabilityView:
    canonical_id: str
    kind: str
    display_name: str
    exposure: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentRuntimeSnapshot:
    schema_id: str
    schema_version: str
    artifact_kind: str
    runtime_revision: str
    capabilities: tuple[AgentCapabilityView, ...]


@dataclass(frozen=True, slots=True)
class VerifiedRuntimeAuthority:
    session_id: str
    runtime_fingerprint: str
    risk: RiskLevel
    runtime_policy_snapshot_id: str
    verification_receipt_digest: str


@dataclass(frozen=True, slots=True)
class RuntimeContextSyncRequest:
    authority: VerifiedRuntimeAuthority
    host_snapshot_ref: str | None
    plugin_handshake_ref: str | None
    agent_runtime_snapshot: AgentRuntimeSnapshot


@dataclass(frozen=True, slots=True)
class SyncRuntimeContextResult:
    snapshot: CapabilitySnapshot
    drift: tuple[CapabilityDrift, ...]
    provider_failures: tuple[ProviderFailure, ...]
    cache_used: bool
    degraded: bool
```

`RuntimeContextSyncRequest` is server-internal and accepts one `VerifiedRuntimeAuthority` issued by Plan 03 authority repository；there are no loose inner session/fingerprint/risk fields for a transport decoder to trust。`NativeHostProvider` production constructor accepts `(HostRuntimeVerifier, host_snapshot_ref, authority)` and calls `resolve(ref, authority.session_id, authority.verification_receipt_digest)` inside timed `discover()`；only the verified return may assert host authorization/policy eligibility/not-exposed。`PluginHandshakeProvider` follows the same pattern。`from_verified()` is test/internal only。`AgentRuntimeSnapshot`/view have strict versioned decoders and no authority fields。Cache remains lower trust and cannot promote state。

- [ ] **Step 4: Implement verified provider composition and typed sync result**

```python
# packages/router-core/src/workflow_skill_router/capabilities/runtime_context.py
class RuntimeContextService:
    def __init__(self, host_verifier, handshake_verifier, snapshot_reader, filesystem_providers, discovery_factory):
        self._host_verifier = host_verifier
        self._handshake_verifier = handshake_verifier
        self._snapshot_reader = snapshot_reader
        self._filesystem_providers = tuple(filesystem_providers)
        self._discovery_factory = discovery_factory

    def sync_verified(self, request: RuntimeContextSyncRequest) -> SyncRuntimeContextResult:
        providers = [AgentRuntimeSnapshotProvider(request.agent_runtime_snapshot), *self._filesystem_providers]
        if request.host_snapshot_ref is not None:
            providers.append(NativeHostProvider(
                self._host_verifier, request.host_snapshot_ref, request.authority
            ))
        if request.plugin_handshake_ref is not None:
            providers.append(PluginHandshakeProvider(
                self._handshake_verifier, request.plugin_handshake_ref, request.authority
            ))
        previous = self._snapshot_reader.latest(request.authority.runtime_fingerprint)
        if previous is not None:
            providers.append(CachedSnapshotProvider(previous))
        discovery = self._discovery_factory(tuple(providers))
        found = discovery.discover(
            DiscoveryContext(request.authority.runtime_fingerprint, request.authority.risk), previous=previous
        )
        failures = tuple(ProviderFailure.from_discovery(item) for item in found.provider_failures)
        return SyncRuntimeContextResult(
            snapshot=found.snapshot,
            drift=found.drift,
            provider_failures=failures,
            cache_used=previous is not None,
            degraded=bool(failures) or found.used_degraded_provider,
        )
```

The `SnapshotReader` is a Protocol in this plan；Plan 03 supplies its SQLite implementation。The discovery factory applies explicit deadlines to the entire `provider.discover()` call—including verifier resolution: native host and agent runtime 250 ms、plugin handshake 500 ms、filesystem 1,500 ms、cache 100 ms。No verifier is called on the coordinator thread before submission。Timeout/cancellation becomes `ProviderFailure(reason_code="provider-timeout")` and never disappears from `SyncRuntimeContextResult`；late completion cannot mutate the already-returned snapshot。If every authoritative provider fails, a cache-only snapshot remains `degraded`/`stale` according to risk and can never become `available` for R2/R3。

- [ ] **Step 5: Run concrete provider, timeout, UTF-8, and complete capability tests**

Run:

```bash
python -m unittest packages/router-core/tests/capabilities/test_runtime_providers.py packages/router-core/tests/capabilities/test_runtime_context.py -v
python -m unittest discover -s packages/router-core/tests/capabilities -p "test_*.py" -v
```

Expected: all tests PASS；handshake schema drift changes the fingerprint、provider timeout is observable、cache non-promotion uses real provider classes、and Traditional Chinese metadata round-trips as UTF-8。

- [ ] **Step 6: Commit the executable runtime-discovery slice**

```bash
git add packages/router-core/src/workflow_skill_router/capabilities packages/router-core/tests/capabilities
git commit -m "feat(core): discover verified runtime capabilities"
```

## Self-Review Record

- Spec coverage: Task 1 covers §22.2 compatibility boundary; Task 2 covers §13.1/§22 versioned artifact identity; Tasks 3–6 cover §10.1–§10.6, scanner safety, all five provider classes, verified runtime sync, immutable snapshot, drift, timeout/degraded behavior, UTF-8, source-qualified identity, 1,000-capability performance, and §26.4 acceptance criteria。
- Explicitly deferred without overlap: route／consent go to plan 02；state／Goal／SQLite go to plans 03；MCP／CLI／fallback go to plan 04；evaluation goes to plan 05。This plan exports the exact immutable contracts those plans consume。
- 禁止樣板詞掃描：0 matches；each code-producing step names concrete files, functions, commands, and expected red／green outcomes。
- Type consistency: `ArtifactEnvelope` uses `Mapping[str, Any]`; registry discriminator is always the same three-string tuple；`CapabilitySnapshot` is the single snapshot type exported to route/state/evaluation；all timestamps are timezone-aware internally and serialized as UTF-8 ISO-8601 strings。
- Security review: the body-read guard, invalid body UTF-8 case, bounded header, trusted root resolution, cache non-promotion, source-qualified identity, deterministic merge, and explicit provider failure paths prevent the highest-risk discovery regressions。
