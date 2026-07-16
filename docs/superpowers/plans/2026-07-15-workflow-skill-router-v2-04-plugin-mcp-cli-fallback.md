# Workflow Skill Router V2 Plugin、MCP、CLI 與 Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將同一套 Python Router core 封裝成可安裝 Codex Plugin、十工具 MCP server、跨平台 CLI 與純 SKILL fallback，並在 Windows、macOS、Linux 驗證一致行為。

**Architecture:** Plugin 由官方 `plugin-creator` scaffold 起步；Python core 以 deterministic `.pyz` 交付，Node MCP server 只負責 stable SDK transport、Python 3.11 discovery 與 persistent JSONL bridge，所有 routing/state/consent policy 只存在 Python core。Python 或 MCP 無法啟動時讓 host 停用 MCP，但 Plugin 內的 SKILL 仍以明示降級的文字 protocol 工作。

**Tech Stack:** Python 3.11+ stdlib、zipapp-compatible `.pyz`、Node.js 24、`@modelcontextprotocol/sdk@1.29.0`、`zod@4.1.12`、`esbuild@0.28.1`、Node `test`、Codex Plugin manifest／`.mcp.json`。

## Global Constraints

- Plugin 固定位於 `plugins/workflow-skill-router/`，且必須先執行 `plugin-creator/scripts/create_basic_plugin.py`，不能手工假造初始 scaffold。
- 本計畫不建立或修改 marketplace；Plugin 初始封裝不等於安裝、登入或 runtime approval。
- `.codex-plugin/plugin.json` 的 `name` 與外層目錄都固定為 `workflow-skill-router`，版本使用 strict semver `2.0.0-alpha.1`。
- Node MCP adapter 鎖定 stable `@modelcontextprotocol/sdk@1.29.0`；不得升級到 MCP SDK v2 beta。
- Runtime core 只有 `packages/router-core/src/workflow_skill_router/` 一份；Node、CLI 與 SKILL 不複製 routing、consent、state 或 Goal policy。
- Node 與 Python 使用一個長存 JSONL child process；每次 MCP tool call 不得重新啟動 Python。
- Windows discovery 順序是 `py -3.11`、`python`；macOS/Linux 是 `python3`、`python`；所有候選必須實際驗證 Python >= 3.11。
- 無 Python、bridge crash 或 MCP unavailable 時保留純 SKILL fallback，並揭露無 durable resume、CAS、完整 drift detection、sealed instrumentation；只能宣稱 `skill-only-fallback`。
- 公開 MCP 工具恰好十個，名稱與核准規格一致；任何 tool 都不能授予 host runtime permission。
- `record_work_event` 只接受 typed observation／command，不是 raw event append API。
- MCP stdout 只能輸出 protocol；diagnostic 一律送 stderr，所有 JSON／文件／測試 fixture 使用 UTF-8。
- `package-lock.json`、`mcp/server.bundle.mjs`、`runtime/workflow_skill_router.pyz` 都要 deterministic 生成並納入 release package。
- 不修改 V1 legacy CLI 的 argparse、environment、stdout/stderr 或 exit code；V2 使用新的 `workflow-skill-router` entry point。

---

## File Structure

```text
packages/router-core/src/workflow_skill_router/
  bridge.py                    # persistent JSONL protocol loop
  plugin_composition.py        # canonical composition.open wrapper
  service_codecs.py            # ten strict request/result codecs
  tool_dispatch.py             # 十工具 JSON -> typed RouterService adapter
  cli/
    __init__.py                # public main() 與 command tree
    __main__.py                # python -m workflow_skill_router.cli
    evaluation.py              # typed evaluation subcommands
  __main__.py                  # .pyz entrypoint
packages/router-core/tests/
  bridge/test_jsonl_bridge.py
  bridge/test_service_codecs.py
  bridge/test_plugin_composition.py
  cli/test_cli.py
  cli/test_console_entrypoint.py
  integration/test_transport_equivalence.py
  plugin/test_plugin_layout.py
plugins/workflow-skill-router/
  .codex-plugin/plugin.json
  .mcp.json
  skills/workflow-skill-router/SKILL.md
  package.json
  package-lock.json
  mcp/src/python-discovery.ts
  mcp/src/core-client.ts
  mcp/src/tool-definitions.ts
  mcp/src/server.ts
  mcp/test/python-discovery.test.ts
  mcp/test/tool-surface.test.ts
  mcp/test/mcp-roundtrip.test.ts
  mcp/server.bundle.mjs
  runtime/workflow_skill_router.pyz
  scripts/build-runtime.py
  scripts/build-mcp.mjs
  scripts/smoke-plugin.mjs
.github/workflows/v2-plugin-smoke.yml
```

## Public Tool Contract

| MCP tool | Python service method | Authorization boundary |
|---|---|---|
| `sync_runtime_context` | `sync_runtime_context(SyncRuntimeContext) -> SyncRuntimeContextResult` | bootstrap/control-plane；驗證 outer session/actor/policy，server 派生 fingerprint/risk，回傳 snapshot+drift+provider failures |
| `plan_work` | `plan_work(PlanWork) -> PlanWorkResult` | bootstrap/control-plane；不能授權執行能力 |
| `get_next_work` | `get_next_work(NextWorkQuery) -> NextWorkResult` | bootstrap/control-plane；檢查 lock 與 entry conditions |
| `validate_route` | `validate_route(ValidateRoute) -> RouteValidationResult` | JIT 驗證 snapshot/lock/consent/risk/content preflight；只簽單次 lease/bound handle |
| `record_work_event` | `record_work_event(RecordWorkEvent) -> RecordWorkEventResult` | reporting；引用 lease/intent/action digest，禁止 raw append |
| `evaluate_gate` | `evaluate_gate(EvaluateGate) -> GateEvaluationResult` | control-plane；CAS 綁 state/plan/evidence，不執行新副作用 |
| `get_router_status` | `get_router_status(RouterStatusQuery) -> RouterStatusView` | read-only；Goal status query 不建立 work |
| `run_model_evaluation` | `run_model_evaluation(RunModelEvaluation) -> EvaluationRunResult` | 獨立 Eval Run authorization；無 adapter 回 `manual-required` |
| `compare_evaluations` | `compare_evaluations(CompareEvaluations) -> EvaluationComparison` | paired manifest 驗證；不用 route lease |
| `export_router_artifact` | `export_router_artifact(ExportRouterArtifact) -> ExportResult` | 無 human attestation 只能 local review draft |

### Task 1: 由 plugin-creator scaffold 並建立 manifest 與純 SKILL fallback

**Files:**
- Create by scaffold: `plugins/workflow-skill-router/.codex-plugin/plugin.json`
- Create by scaffold: `plugins/workflow-skill-router/.mcp.json`
- Create by scaffold: `plugins/workflow-skill-router/skills/`
- Create by scaffold: `plugins/workflow-skill-router/scripts/`
- Create by scaffold: `plugins/workflow-skill-router/assets/`
- Create (canonical): `starter/v2/workflow-skill-router/SKILL.md`
- Create (canonical): `starter/v2/workflow-skill-router/references/routing-protocol.md`
- Create (canonical): `starter/v2/workflow-skill-router/references/goal-protocol.md`
- Create (canonical): `starter/v2/workflow-skill-router/references/evaluation-boundary.md`
- Create: `plugins/workflow-skill-router/scripts/sync-skill.py`
- Generate exact copy: `plugins/workflow-skill-router/skills/workflow-skill-router/**`
- Test: `packages/router-core/tests/plugin/test_plugin_layout.py`

**Interfaces:**
- Consumes: Codex Plugin manifest contract and the approved RequestDecision／Single／Phased／Managed Goal semantics.
- Produces: valid `.codex-plugin/plugin.json`; `.mcp.json` pointing to `node ./mcp/server.bundle.mjs`; canonical V2 fallback under `starter/v2/`; byte-identical Plugin SKILL copy。The existing `starter/workflow-skill-router/` remains the V1 stable source until explicit GA promotion。

- [ ] **Step 1: Write a failing package-layout test before scaffolding**

```python
# packages/router-core/tests/plugin/test_plugin_layout.py
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PLUGIN = ROOT / "plugins" / "workflow-skill-router"


class PluginLayoutTests(unittest.TestCase):
    def test_manifest_and_companions_are_consistent(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("workflow-skill-router", manifest["name"])
        self.assertEqual("2.0.0-alpha.1", manifest["version"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertTrue((PLUGIN / "skills" / "workflow-skill-router" / "SKILL.md").is_file())
        self.assertEqual(
            (ROOT / "starter/v2/workflow-skill-router/SKILL.md").read_bytes(),
            (PLUGIN / "skills/workflow-skill-router/SKILL.md").read_bytes(),
        )
        self.assertNotIn("apps", manifest)
        self.assertNotIn("hooks", manifest)

    def test_mcp_config_uses_bundled_relative_entrypoint(self) -> None:
        config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["workflow-skill-router"]
        self.assertEqual("node", server["command"])
        self.assertEqual(["./mcp/server.bundle.mjs"], server["args"])
        self.assertEqual(".", server["cwd"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm the plugin is absent**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/plugin/test_plugin_layout.py -v
```

Expected: FAIL with `FileNotFoundError` for `plugins/workflow-skill-router/.codex-plugin/plugin.json`.

- [ ] **Step 3: Run the required scaffold command without marketplace mutation**

Run:

```powershell
$Repo = (Resolve-Path ".").Path
$Creator = "C:\Users\erichuang\.codex\skills\.system\plugin-creator\scripts\create_basic_plugin.py"
py -3.11 $Creator workflow-skill-router --path "$Repo\plugins" --with-skills --with-scripts --with-assets --with-mcp
```

Expected output contains `Created plugin scaffold:` and the absolute `plugins\workflow-skill-router` path. Do not add `--with-marketplace`.

- [ ] **Step 4: Replace scaffold defaults with the exact manifest and MCP config**

```json
{
  "name": "workflow-skill-router",
  "version": "2.0.0-alpha.1",
  "description": "依任務規模、Goal 關係、可用能力與使用者指定 SKILL，提供可驗證的工作路由與編排。",
  "author": { "name": "ChiYu" },
  "license": "MIT",
  "keywords": ["codex", "skill-router", "goal", "workflow", "mcp"],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "Workflow Skill Router",
    "shortDescription": "為 Single、Phased 與 Goal 工作選擇最小可驗證能力。",
    "longDescription": "動態發現 runtime capability，尊重 Explicit Skill Lock 與 consent，並以 Phase/Goal state、evidence gate 與真實模型評測改善 Codex 開發流程。",
    "developerName": "ChiYu",
    "category": "Productivity",
    "capabilities": ["Routing", "Goal Orchestration", "Evaluation"],
    "defaultPrompt": [
      "分析這個任務並選擇 Single、Phased 或 Goal 流程。",
      "只使用我指定的 SKILL；需要支援能力時先詢問。",
      "顯示目前 Goal 的下一個可安全執行工作。"
    ]
  }
}
```

```json
{
  "mcpServers": {
    "workflow-skill-router": {
      "command": "node",
      "args": ["./mcp/server.bundle.mjs"],
      "cwd": "."
    }
  }
}
```

- [ ] **Step 5: Write the canonical fallback SKILL contract and generate the Plugin copy**

`starter/v2/workflow-skill-router/SKILL.md` must include valid frontmatter and these executable rules: classify `goal_relation` before task size; choose exactly one of `single|phased|managed-goal`; treat explicit SKILL as an orthogonal lock; never read a recommended support SKILL body before consent; preserve every Phase in medium work; classify every Work Item again in Goal work; short-circuit status; disclose `skill-only-fallback` limits; never lower R2/R3 host approval。The three reference files hold the detailed decision matrix、Goal checklist and evaluation claim boundary；SKILL.md links only to those references needed by the current route。Use this minimum body as the starting implementation:

```markdown
---
name: workflow-skill-router
description: 當 Codex 任務需要依小型、中型、大型或 Goal 模式選擇正確 SKILL、逐階段重新路由，或尊重使用者指定 SKILL 與輔助能力同意時使用。
---

# Workflow Skill Router V2

先解析 Goal relation：`progress`、`steer`、`status`、`side-question`、`unrelated` 或 `none`。`status` 只讀狀態，不建立工作；`side-question` 與 `unrelated` 不修改 Goal semantic revision。

再選 envelope：單一意圖用 `single`；有兩個以上相異階段用 `phased`，每個 Phase 重新選擇能力；長期、可恢復、跨 repo、dependency DAG 或 Goal progress/steer 用 `managed-goal`，每個 Work Item 再分成 single 或 phased。

使用者指定 SKILL 時先鎖定指定項目。Router 推薦的任何額外 SKILL、Plugin 或 MCP 支援，都要先說明用途、scope、拒絕後限制與 context cost，取得同意後才能讀取或啟用。使用者拒絕時只能使用指定能力、限縮成果或誠實阻塞，不可靜默替代。

若 MCP 可用，使用 capability snapshot、route validation、state/gate 與 evidence。若 MCP 不可用，明示目前是 `skill-only-fallback`：沒有 durable resume、CAS、完整 drift detection 或 sealed activation instrumentation；不得宣稱 `hybrid-full`，也不得把不可觀測項目算成通過。

所有 R2/R3 行動仍由 Codex host sandbox、approval 與 permission 控制；SKILL 同意不等於安裝、寫入、部署、傳訊或 production access 授權。
```

After authoring the canonical V2 starter, run `py -3.11 plugins/workflow-skill-router/scripts/sync-skill.py` to generate `plugins/workflow-skill-router/skills/workflow-skill-router/**` from an explicit allowlist。The script refuses unexpected source files and overwrites only the four known destination files；it never recursively deletes。The layout test compares the full relative-file set and every SHA-256, so Plugin and standalone Skill cannot drift。

- [ ] **Step 6: Validate and commit the scaffold slice**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/plugin/test_plugin_layout.py -v
py -3.11 "C:\Users\erichuang\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" "plugins/workflow-skill-router"
```

Expected: layout tests PASS and validator prints a valid plugin result with no manifest errors.

```powershell
git add starter/v2/workflow-skill-router plugins/workflow-skill-router packages/router-core/tests/plugin/test_plugin_layout.py
git commit -m "feat(plugin): scaffold workflow skill router"
```

### Task 2: 建立 Python JSONL bridge 與 deterministic `.pyz`

**Files:**
- Modify: `packages/router-core/pyproject.toml`
- Create: `packages/router-core/src/workflow_skill_router/tool_dispatch.py`
- Create: `packages/router-core/src/workflow_skill_router/service_codecs.py`
- Create: `packages/router-core/src/workflow_skill_router/bridge.py`
- Create: `packages/router-core/src/workflow_skill_router/plugin_composition.py`
- Create: `packages/router-core/src/workflow_skill_router/cli/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/cli/__main__.py`
- Create: `packages/router-core/src/workflow_skill_router/cli/evaluation.py`
- Create: `packages/router-core/src/workflow_skill_router/__main__.py`
- Create: `plugins/workflow-skill-router/scripts/build-runtime.py`
- Generate: `plugins/workflow-skill-router/runtime/workflow_skill_router.pyz`
- Test: `packages/router-core/tests/bridge/test_jsonl_bridge.py`
- Test: `packages/router-core/tests/bridge/test_service_codecs.py`
- Test: `packages/router-core/tests/bridge/test_plugin_composition.py`
- Test: `packages/router-core/tests/bridge/test_runtime_archive.py`
- Test: `packages/router-core/tests/cli/test_console_entrypoint.py`

**Interfaces:**
- Consumes: all ten typed methods on `RouterService`; seven come from plan 03 and evaluation/export three come from plan 05。Therefore plan 05 must finish before this plan's bridge/runtime tasks。
- Produces: request `{request_id, tool, arguments}` -> response `{request_id, ok, result}` or `{request_id, ok:false, error:{code,message}}`; concrete `build_service_codec_registry() -> Mapping[str, ServiceCodec]`; `ToolDispatcher.dispatch(tool: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]`; `open_plugin_service(...)` with concrete Plan 05 evaluation composition；canonical `workflow-skill-router = workflow_skill_router.cli:main` console entry point and equivalent package `python -m workflow_skill_router`; CLI command `serve-jsonl`.

- [ ] **Step 1: Write a failing persistent-bridge test**

```python
# packages/router-core/tests/bridge/test_jsonl_bridge.py
import io
import json
import unittest

from workflow_skill_router.bridge import serve


class FakeDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    def dispatch(self, tool, arguments):
        self.calls += 1
        return {"tool": tool, "sequence": self.calls, "arguments": arguments}


class BridgeTests(unittest.TestCase):
    def test_two_requests_share_one_dispatcher_process(self) -> None:
        source = io.StringIO(
            '{"request_id":"r1","tool":"get_router_status","arguments":{}}\n'
            '{"request_id":"r2","tool":"get_router_status","arguments":{}}\n'
        )
        output = io.StringIO()
        serve(source, output, FakeDispatcher())
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([1, 2], [row["result"]["sequence"] for row in rows])
        self.assertTrue(all(row["ok"] for row in rows))

    def test_unknown_tool_fails_closed_without_traceback_or_secret_echo(self) -> None:
        source = io.StringIO('{"request_id":"r1","tool":"raw_append","arguments":{"token":"secret"}}\n')
        output = io.StringIO()
        serve(source, output, FakeDispatcher())
        row = json.loads(output.getvalue())
        self.assertFalse(row["ok"])
        self.assertEqual("unknown-tool", row["error"]["code"])
        self.assertNotIn("secret", output.getvalue())
```

- [ ] **Step 2: Run the test and confirm bridge modules are absent**

Run: `py -3.11 -m unittest packages/router-core/tests/bridge/test_jsonl_bridge.py -v`

Expected: FAIL with missing `workflow_skill_router.bridge`.

- [ ] **Step 3: Implement the exact ten-tool dispatcher and line protocol**

```python
# packages/router-core/src/workflow_skill_router/tool_dispatch.py
from __future__ import annotations

from typing import Any, Mapping

from workflow_skill_router.service_codecs import build_service_codec_registry


PUBLIC_TOOLS = (
    "sync_runtime_context", "plan_work", "get_next_work", "validate_route",
    "record_work_event", "evaluate_gate", "get_router_status",
    "run_model_evaluation", "compare_evaluations", "export_router_artifact",
)


class ToolDispatcher:
    def __init__(self, service) -> None:
        self._service = service
        self._codecs = build_service_codec_registry()

    def dispatch(self, tool: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if tool not in PUBLIC_TOOLS:
            raise LookupError(tool)
        command = self._codecs[tool].decode(arguments)
        result = getattr(self._service, tool)(command)
        return self._codecs[tool].encode(result)
```

`service_codecs.py` provides one explicit codec per public tool, mapped to the exact frozen command/result types from plans 03/05。Each decoder requires versioned discriminators, rejects unknown/missing fields, constructs nested dataclasses/enums without `**payload` trust, and never accepts server-owned fields such as inner session/runtime fingerprint/risk、trusted、allowed availability、actual values、raw event fields、review authority or verifier。The sync result codec serializes all `SyncRuntimeContextResult` fields (`snapshot`, stable-sorted `drift`, `provider_failures`, `cache_used`, `degraded`)；it cannot collapse back to `CapabilitySnapshot`。`test_service_codecs.py` round-trips all ten valid examples and proves every forbidden field fails with `invalid-arguments`。

`plugin_composition.py` defines `open_plugin_service(state_dir, bridge_initialization_ref, host_registry_verifier) -> RouterService`。The verifier resolves a signed `VerifiedBridgeInitialization` bound to bundle/schema digest、session、runtime revision and allowed adapter registrations；raw initialization JSON cannot assert host authorization or inject Python objects。`build_evaluation_ports()` constructs all sixteen Plan 05 fields：SQLite authorization/evaluation stores and authorizers、verified adapter registry、restricted worker broker、isolation verifier、cancellation、scoring key/release policy/scorer、stable trace/collection verifiers and a server-owned `ReviewVerifierRegistry`。The review registry starts reject-by-default and accepts host/external verifier entries only from the signed verified initialization with pinned authority/key/revocation metadata。The request/CLI can never register or select a verifier。

`open_plugin_service` then delegates exactly once to the final canonical `composition.open(...)` with concrete SQLite/artifact paths、runtime/handshake verifier registry、request authorizer、instruction/runtime-contract resolver、shared artifact protector、activation preflight、the complete evaluation aggregate、clock/id factory。Host/session/isolation/review receipts remain server-verified per request。No `RouterService.open()` alternate constructor exists。`test_plugin_composition.py` proves all routing/evaluation ports are wired, state stays outside plugin cache, invalid bundle digest fails, missing kind-specific activation support does not claim `hybrid-full`, default review publication rejects, a verified host registry can validate an opaque signed human receipt, and a client-provided verifier/authority/key override is rejected before service construction。

Add this exact packaging entry point while preserving the package-data declarations from plans 01/03:

```toml
[project.scripts]
workflow-skill-router = "workflow_skill_router.cli:main"
```

`workflow_skill_router.cli.__init__` exports `main()`；`cli.__main__` calls it and `cli.evaluation` owns the nested evaluation request parsers without duplicating service policy。`test_console_entrypoint.py` builds a wheel into a temporary directory, installs it into a fresh temporary virtual environment, and proves `workflow-skill-router --help`、`python -m workflow_skill_router --help`、`python -m workflow_skill_router.cli --help` and direct `workflow_skill_router.cli.main(["--help"])` expose the same command tree and exit contract。No test may depend on `PYTHONPATH` for this packaging check。

`bridge.py` must parse one UTF-8 JSON object per line, cap each line at 4 MiB, require non-empty string `request_id` and `tool`, validate `tool` against `PUBLIC_TOOLS` before invoking even a test dispatcher, reject duplicate in-flight IDs, never echo input on error, and flush exactly one response line per request. Map `LookupError` to `unknown-tool`, schema errors to `invalid-arguments`, optimistic conflict to `state-conflict`, and unexpected errors to `internal-error` with only a correlation ID on stdout; detailed diagnostic goes to stderr.

- [ ] **Step 4: Build a deterministic runtime archive without copying policy**

`build-runtime.py` reads a deterministic allowlist from tracked files under `packages/router-core/src/workflow_skill_router`：only `.py` source plus package JSON Schema／SQL migration resources declared by `pyproject.toml` are eligible。It rejects untracked files、symlinks/reparse points、paths outside source root、`__pycache__`、`.pyc/.pyo`、coverage/cache/editor files and any unexpected extension。It sorts normalized archive paths, uses ZIP timestamp `(1980, 1, 1, 0, 0, 0)`, fixed Unix modes, UTF-8 source bytes and `ZIP_STORED` so interpreter/zlib/platform revisions cannot change bytes。A generated top-level `__main__.py` contains `from workflow_skill_router.cli import main; main()`。The builder writes one explicit same-directory temporary file, fsyncs and atomically replaces `runtime/workflow_skill_router.pyz`; failure may remove only that named temp file, never a tree/wildcard。

`test_runtime_archive_is_source_only_and_compileall_invariant` records the archive digest, runs `compileall` on the source tree, rebuilds, and asserts the digest/member list is identical and contains no cache/bytecode member。A deliberately untracked `.py` fixture and tracked unexpected extension both fail closed。Three-OS CI compares the manifest/archive SHA-256, not merely successful execution。

Run:

```powershell
py -3.11 plugins/workflow-skill-router/scripts/build-runtime.py
$First = (Get-FileHash plugins/workflow-skill-router/runtime/workflow_skill_router.pyz -Algorithm SHA256).Hash
py -3.11 plugins/workflow-skill-router/scripts/build-runtime.py
$Second = (Get-FileHash plugins/workflow-skill-router/runtime/workflow_skill_router.pyz -Algorithm SHA256).Hash
if ($First -ne $Second) { throw "pyz build 不可重現" }
py -3.11 plugins/workflow-skill-router/runtime/workflow_skill_router.pyz --help
```

Expected: hashes match and the final output lists `serve-jsonl`, `doctor`, `status`, `plan`, `validate-route`, and `evaluation`；`evaluation` contains `run|import|compare|export|publish|export-status` subcommands。The builder also implements `--check`, which builds bytes in memory and exits nonzero when they differ from the committed archive.

- [ ] **Step 5: Run bridge tests and commit**

Run: `py -3.11 -m unittest packages/router-core/tests/bridge/test_jsonl_bridge.py packages/router-core/tests/bridge/test_service_codecs.py packages/router-core/tests/bridge/test_plugin_composition.py packages/router-core/tests/bridge/test_runtime_archive.py packages/router-core/tests/cli/test_console_entrypoint.py -v`

Expected: all bridge tests PASS and two requests are served by one dispatcher instance.

```powershell
git add packages/router-core/pyproject.toml packages/router-core/src/workflow_skill_router/bridge.py packages/router-core/src/workflow_skill_router/plugin_composition.py packages/router-core/src/workflow_skill_router/service_codecs.py packages/router-core/src/workflow_skill_router/tool_dispatch.py packages/router-core/src/workflow_skill_router/cli packages/router-core/src/workflow_skill_router/__main__.py packages/router-core/tests/bridge/test_jsonl_bridge.py packages/router-core/tests/bridge/test_service_codecs.py packages/router-core/tests/bridge/test_plugin_composition.py packages/router-core/tests/bridge/test_runtime_archive.py packages/router-core/tests/cli/test_console_entrypoint.py plugins/workflow-skill-router/scripts/build-runtime.py plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "feat(plugin): bundle persistent python router runtime"
```

### Task 3: 實作 stable SDK Node MCP transport 與 persistent child client

**Files:**
- Create: `plugins/workflow-skill-router/package.json`
- Create: `plugins/workflow-skill-router/package-lock.json`
- Create: `plugins/workflow-skill-router/mcp/src/python-discovery.ts`
- Create: `plugins/workflow-skill-router/mcp/src/state-path.ts`
- Create: `plugins/workflow-skill-router/mcp/src/core-client.ts`
- Create: `plugins/workflow-skill-router/mcp/src/tool-schemas.ts`
- Create: `plugins/workflow-skill-router/mcp/src/tool-definitions.ts`
- Create: `plugins/workflow-skill-router/mcp/src/server.ts`
- Create: `plugins/workflow-skill-router/scripts/build-mcp.mjs`
- Generate: `plugins/workflow-skill-router/mcp/server.bundle.mjs`
- Test: `plugins/workflow-skill-router/mcp/test/python-discovery.test.ts`
- Test: `plugins/workflow-skill-router/mcp/test/state-path.test.ts`
- Test: `plugins/workflow-skill-router/mcp/test/core-client.test.ts`
- Test: `plugins/workflow-skill-router/mcp/test/tool-surface.test.ts`

**Interfaces:**
- Consumes: Python JSONL request/response from Task 2 and `runtime/workflow_skill_router.pyz`.
- Produces: `discoverPython(platform, probe) -> Promise<PythonCommand>`; singleton `CoreClient.start/call/close` with bounded call deadline/restart semantics；ten distinct typed Zod input shapes derived from the versioned service contracts；MCP `ListTools` containing exactly `PUBLIC_TOOL_NAMES`; bundled ESM entrypoint.

- [ ] **Step 1: Write failing Node tests for discovery order and exact tool surface**

```typescript
// plugins/workflow-skill-router/mcp/test/tool-surface.test.ts
import assert from "node:assert/strict";
import test from "node:test";
import { PUBLIC_TOOL_NAMES } from "../src/tool-definitions.js";

test("只公開核准的十個工具", () => {
  assert.deepEqual(PUBLIC_TOOL_NAMES, [
    "sync_runtime_context", "plan_work", "get_next_work", "validate_route",
    "record_work_event", "evaluate_gate", "get_router_status",
    "run_model_evaluation", "compare_evaluations", "export_router_artifact",
  ]);
  assert.equal(new Set(PUBLIC_TOOL_NAMES).size, 10);
});
```

`python-discovery.test.ts` must assert Windows candidates are `[["py","-3.11"],["python"]]`, POSIX candidates are `[["python3"],["python"]]`, Python 3.10 is rejected, Python 3.11+ is accepted, and `WORKFLOW_SKILL_ROUTER_PYTHON` is an exclusive explicit override rather than a shell command string.

`state-path.test.ts` must prove the database is never written inside the Plugin cache/package。`WORKFLOW_SKILL_ROUTER_DATA_DIR` is an explicit directory override; otherwise resolve to `%LOCALAPPDATA%/Codex/workflow-skill-router` on Windows、`~/Library/Application Support/Codex/workflow-skill-router` on macOS、and `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` on Linux。Create only the exact selected directory, reject a path that resolves inside the Plugin root, and pass `<data-dir>/router-v2.sqlite3` to Python。

- [ ] **Step 2: Run tests and confirm package/source is absent**

Run:

```powershell
Set-Location plugins/workflow-skill-router
npm test
```

Expected: FAIL because `package.json` and TypeScript source do not exist.

- [ ] **Step 3: Pin dependencies and deterministic build commands**

```json
{
  "name": "workflow-skill-router-plugin-runtime",
  "version": "2.0.0-alpha.1",
  "private": true,
  "type": "module",
  "engines": { "node": ">=24" },
  "scripts": {
    "build": "node ./scripts/build-mcp.mjs",
    "test": "node ./scripts/build-mcp.mjs --tests && node --test ./.test-build/python-discovery.test.mjs ./.test-build/state-path.test.mjs ./.test-build/core-client.test.mjs ./.test-build/tool-surface.test.mjs ./.test-build/mcp-roundtrip.test.mjs",
    "check": "npm run build && npm test"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "1.29.0",
    "zod": "4.1.12"
  },
  "devDependencies": {
    "esbuild": "0.28.1"
  }
}
```

Run `npm install --package-lock-only` once and commit the lock. `build-mcp.mjs` bundles `mcp/src/server.ts` for `platform:"node"`, `format:"esm"`, `target:"node24"`, `bundle:true`, `sourcemap:false`, and writes only `mcp/server.bundle.mjs`. `--tests` bundles each known test entry to a fixed `.test-build/<name>.test.mjs`; do not use an output-directory cleanup operation.

- [ ] **Step 4: Implement Python discovery and one persistent JSONL child**

```typescript
// plugins/workflow-skill-router/mcp/src/python-discovery.ts
export type PythonCommand = Readonly<{ command: string; prefixArgs: readonly string[] }>;

export function candidates(platform: NodeJS.Platform): readonly PythonCommand[] {
  return platform === "win32"
    ? [{ command: "py", prefixArgs: ["-3.11"] }, { command: "python", prefixArgs: [] }]
    : [{ command: "python3", prefixArgs: [] }, { command: "python", prefixArgs: [] }];
}
```

`discoverPython` probes `-c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"` with `shell:false`, a 3-second timeout and no inherited stdin. If `WORKFLOW_SKILL_ROUTER_PYTHON` is set, treat it as one executable path with zero shell parsing and do not try other candidates。`CoreClient.start()` calls discovery once, spawns `[...prefixArgs, pyz, "serve-jsonl", "--database", database]`, keeps a `Map<request_id, Promise handlers>`, splits stdout on newline, writes requests with backpressure handling, rejects all pending calls on child exit, and never logs request payloads。

`CoreClient.call(tool, arguments, {signal})` applies a server-owned `CallDeadlinePolicy` from verified Plugin initialization：short control calls have a bounded seconds deadline and evaluation calls may use a longer but finite ceiling consistent with Plan 05 run deadline。On abort/deadline it atomically marks the generation unhealthy, terminates the exact Python child, rejects every pending request with typed `cancelled|bridge-timeout|bridge-restarted`, waits for exit, and lazily starts a fresh generation for the next call；request IDs include generation and cannot accept late output。It never leaves a hung child serving later calls。`core-client.test.ts` uses a fake child that never answers, proves bounded rejection/termination/no orphan, then proves the next status call succeeds on a fresh child；it also proves aborting one multiplexed generation cannot resolve another request with stale output。

- [ ] **Step 5: Register exactly ten MCP tools with one generic transport handler**

```typescript
// plugins/workflow-skill-router/mcp/src/tool-definitions.ts
import { TOOL_INPUT_SHAPES } from "./tool-schemas.js";

export const PUBLIC_TOOL_NAMES = [
  "sync_runtime_context", "plan_work", "get_next_work", "validate_route",
  "record_work_event", "evaluate_gate", "get_router_status",
  "run_model_evaluation", "compare_evaluations", "export_router_artifact",
] as const;

export const TOOL_DEFINITIONS = PUBLIC_TOOL_NAMES.map((name) => ({
  name,
  description: `Workflow Skill Router V2：${name}`,
  inputSchema: TOOL_INPUT_SHAPES[name],
}));
```

`tool-schemas.ts` must define a distinct raw Zod shape for every tool instead of a generic `payload` bag。All control-plane calls include outer `session_id`、`actor`、`runtime_policy_snapshot_id`; mutations also require `expected_state_version`、`idempotency_key`、`correlation_id`。`sync_runtime_context` accepts only typed intent refs plus strict `AgentRuntimeSnapshot` and rejects nested `session_id`、`runtime_fingerprint`、risk/authority fields。Other shapes add their exact tool-specific fields。`tool-surface.test.ts` proves all ten reject empty/unknown fields, sync rejects forged inner identity, and `record_work_event` rejects raw event fields。

```typescript
// plugins/workflow-skill-router/mcp/src/server.ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CoreClient } from "./core-client.js";
import { TOOL_DEFINITIONS } from "./tool-definitions.js";

const core = new CoreClient();
await core.start();
const server = new McpServer({ name: "workflow-skill-router", version: "2.0.0-alpha.1" });
for (const definition of TOOL_DEFINITIONS) {
  server.registerTool(
    definition.name,
    { description: definition.description, inputSchema: definition.inputSchema },
    async (arguments_) => {
      const result = await core.call(definition.name, arguments_);
      return { content: [{ type: "text", text: JSON.stringify(result) }], structuredContent: result };
    },
  );
}
process.once("SIGINT", async () => { await core.close(); process.exit(0); });
process.once("SIGTERM", async () => { await core.close(); process.exit(0); });
await server.connect(new StdioServerTransport());
```

If Python discovery fails before transport connects, write one Traditional Chinese stderr line containing `skill-only-fallback` and exit code 78. Do not implement a second router in Node; the Plugin SKILL remains discoverable by Codex.

- [ ] **Step 6: Build, test dependency pins, and commit**

Run:

```powershell
Set-Location plugins/workflow-skill-router
npm install --package-lock-only
npm ci
npm run check
npm ls @modelcontextprotocol/sdk zod esbuild --depth=0
```

Expected: Node tests PASS; dependency tree shows exactly SDK `1.29.0`, zod `4.1.12`, esbuild `0.28.1`; bundle exists at `mcp/server.bundle.mjs`.

```powershell
git add plugins/workflow-skill-router/package.json plugins/workflow-skill-router/package-lock.json plugins/workflow-skill-router/mcp plugins/workflow-skill-router/scripts/build-mcp.mjs
git commit -m "feat(plugin): expose stable mcp transport"
```

### Task 4: 完成 V2 CLI、MCP round-trip 與 honest fallback

**Files:**
- Modify: `packages/router-core/src/workflow_skill_router/cli/__init__.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/evaluation.py`
- Test: `packages/router-core/tests/cli/test_cli.py`
- Test: `packages/router-core/tests/integration/test_transport_equivalence.py`
- Test: `plugins/workflow-skill-router/mcp/test/mcp-roundtrip.test.ts`
- Create: `plugins/workflow-skill-router/scripts/smoke-plugin.mjs`

**Interfaces:**
- Consumes: canonical `open_plugin_service(...)` wrapper over Plan 03 `composition.open(...)`; `ToolDispatcher`; Node `CoreClient`; Plan 05 frozen evaluation request/result schemas。
- Produces: `workflow-skill-router` commands `serve-jsonl|doctor|status|plan|validate-route|evaluation`；nested evaluation commands `run|import|compare|export|publish|export-status`；JSON stdout contract；fallback exit 78 contract.

- [ ] **Step 1: Write CLI and MCP integration tests**

```python
# packages/router-core/tests/cli/test_cli.py
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


class CliTests(unittest.TestCase):
    def test_doctor_reports_runtime_and_no_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "workflow_skill_router", "doctor", "--database", str(Path(directory) / "router.db")],
                text=True, encoding="utf-8", capture_output=True, check=False,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("core-ready", payload["runtime_status"])
        self.assertIsNone(payload["conformance_profile"])
        self.assertFalse(payload["telemetry_enabled"])

    def test_v1_scripts_are_not_wrapped_or_reinterpreted(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "packages/router-core/src/workflow_skill_router/cli").glob("*.py")
        )
        for legacy in ("scan-skills.py", "evaluate-routing.py", "validate-router.py"):
            self.assertNotIn(legacy, sources)

    def test_versioned_input_file_and_stdin_have_identical_decoding(self) -> None:
        for command, fixture in EVALUATION_COMMAND_FIXTURES.items():
            from_file = run_cli_with_fresh_state("evaluation", command, "--input", fixture)
            from_stdin = run_cli_with_fresh_state("evaluation", command, stdin=fixture.read_bytes())
            self.assertEqual(normalize_instance_fields(from_file), normalize_instance_fields(from_stdin))

    def test_evaluation_rejects_alternate_flags_and_embedded_authority(self) -> None:
        for command in ("run", "import", "compare", "export", "publish", "export-status"):
            self.assertEqual(2, run_cli("evaluation", command, "--suite", "forbidden.json").returncode)
        self.assertInvalidInput({"authorization": {}, "trusted": True, "runtime_fingerprint": "forged"})
```

The MCP round-trip test must launch the bundled server through SDK `StdioClientTransport`, assert `listTools()` returns the exact ten names, call `get_router_status` against a temporary DB, then close and verify one Python child served all calls. A second test sets `WORKFLOW_SKILL_ROUTER_PYTHON` to a guaranteed missing executable and asserts exit 78 plus stderr containing `skill-only-fallback`, with no JSON protocol text on stdout.

`test_transport_equivalence.py` feeds the same canonical Small、Medium explicit-SKILL rejection and Managed Goal fixtures through direct `RouterService`、CLI JSON input、MCP codecs and pure-SKILL fallback transcript validation。It compares normalized decision/envelope/lock/consent/Goal authority—not transport metadata—and fails if any transport implements a second policy。CLI tests use a fresh state directory per file/stdin run；they additionally execute manual-required→import, verify one-time token same-key replay/different-key rejection, and prove `publish` accepts only opaque attestation ref, never a plain file path。

- [ ] **Step 2: Run tests and confirm CLI/MCP behavior is incomplete**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/cli/test_cli.py -v
Set-Location plugins/workflow-skill-router
npm test
```

Expected: FAIL because CLI subcommands/round-trip smoke are not complete.

- [ ] **Step 3: Implement explicit CLI exit and output contracts**

The `cli/` package uses `argparse` subparsers and never imports V1 scripts。It opens service only through `open_plugin_service()`/canonical composition。Each command accepts state location；mutations require one versioned typed command from `--input <UTF-8 JSON path>` or stdin, not alternate flags。A valid manual/review-required result exits 0；schema/user=2、state conflict=3、integrity/policy=65、missing runtime=78、internal=70。Direct doctor reports core-ready but `conformance_profile=null` until actual MCP handshake plus bound-content preflight prove `hybrid-full`；otherwise it reports `content-preflight-unavailable` or `skill-only-fallback` explicitly, with telemetry false and no environment values。

`serve-jsonl` is the only command that loops. `evaluation run` must preserve `manual-required` returned by the Execution Adapter rather than reporting completion；`evaluation import` validates a sealed manual bundle, execution trace, provenance and authorization before persistence。`evaluation export` without valid human review attestation labels the artifact `review-draft`；`evaluation publish` succeeds only through the trusted attestation verifier, and `evaluation export-status` can publish a score-free `manual-required|review-required` disclosure。

Pure-SKILL fallback has no atomic bound-content handle。It must say content preflight/invocation enforcement is unobservable, require a new route decision for each activation, and never claim `hybrid-full`；R2/R3 remain blocked on host approval/preflight rather than being lowered by fallback。

- [ ] **Step 4: Add plugin smoke script and prove fallback does not duplicate policy**

`smoke-plugin.mjs` must:

1. verify manifest path references exist;
2. verify `package-lock.json` resolves the three pinned versions;
3. build `.pyz` and MCP bundle twice and compare SHA-256;
4. start MCP, list exactly ten tools, and call `get_router_status`;
5. force missing Python and verify exit 78／`skill-only-fallback`;
6. scan Node source for routing decision constants (`single`, `phased`, `managed-goal`, `ConsentGrant`) and fail if they occur outside descriptions/tests, proving policy remains in Python/SKILL;
7. assert stdout contains no diagnostic text during protocol operation.

- [ ] **Step 5: Run full local integration and commit**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 -m unittest packages/router-core/tests/cli/test_cli.py packages/router-core/tests/integration/test_transport_equivalence.py -v
py -3.11 plugins/workflow-skill-router/scripts/build-runtime.py
Set-Location plugins/workflow-skill-router
npm ci
npm run check
node ./scripts/smoke-plugin.mjs
```

Expected: all tests PASS; missing Python path exits 78 while SKILL remains in manifest; normal round-trip calls Python core.

```powershell
git add packages/router-core/src/workflow_skill_router/cli packages/router-core/tests/cli/test_cli.py packages/router-core/tests/integration/test_transport_equivalence.py plugins/workflow-skill-router/mcp/test/mcp-roundtrip.test.ts plugins/workflow-skill-router/scripts/smoke-plugin.mjs plugins/workflow-skill-router/mcp/server.bundle.mjs plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "feat(plugin): add cli and fallback smoke gates"
```

### Task 5: 加入 Windows、macOS、Linux smoke 與 final plugin validation

**Files:**
- Create: `.github/workflows/v2-plugin-smoke.yml`
- Modify: `packages/router-core/tests/plugin/test_plugin_layout.py`

**Interfaces:**
- Consumes: committed deterministic artifacts and all Task 1–4 test commands.
- Produces: three-OS proof for Python discovery、`.pyz`、MCP stdio、CLI UTF-8 and fallback; local plugin-creator validation evidence.

- [ ] **Step 1: Extend the package test to fail on stale generated artifacts**

Add tests that build `.pyz` and bundle into temporary paths, compare hashes to committed artifacts, inspect ZIP entries for traversal/absolute paths, decode all text entries as UTF-8, and assert no access token/private key fixture is present. Run the test before regeneration and expect a stale-artifact assertion failure.

- [ ] **Step 2: Add the dedicated matrix workflow**

```yaml
# .github/workflows/v2-plugin-smoke.yml
name: V2 Plugin Smoke
on:
  pull_request:
  push:
    branches: [main]
jobs:
  smoke:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest, ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - uses: actions/setup-node@v6
        with:
          node-version: "24"
          cache: npm
          cache-dependency-path: plugins/workflow-skill-router/package-lock.json
      - name: Build deterministic Python runtime
        run: python plugins/workflow-skill-router/scripts/build-runtime.py --check
      - name: Test Python core and CLI
        env:
          PYTHONPATH: packages/router-core/src
        run: python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v
      - name: Build and test MCP
        working-directory: plugins/workflow-skill-router
        run: npm ci && npm run check && node ./scripts/smoke-plugin.mjs
```

On Windows, add a test assertion that discovery selects `py -3.11` when available; on macOS/Linux assert it selects `python3`. Also test the second candidate by injecting a probe where the first is absent. Do not depend on OS shell parsing.

- [ ] **Step 3: Regenerate, run all local gates, and validate with plugin-creator**

Run:

```powershell
$env:PYTHONPATH = "packages/router-core/src"
py -3.11 plugins/workflow-skill-router/scripts/build-runtime.py
Push-Location plugins/workflow-skill-router
npm ci
npm run build
npm test
node ./scripts/smoke-plugin.mjs
Pop-Location
py -3.11 -m unittest discover -s packages/router-core/tests -p "test_*.py" -v
py -3.11 "C:\Users\erichuang\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" "plugins/workflow-skill-router"
git diff --exit-code -- plugins/workflow-skill-router/mcp/server.bundle.mjs plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
```

Expected: all tests PASS; plugin validator passes; final `git diff --exit-code` is clean, proving generated runtime artifacts are current.

- [ ] **Step 4: Commit the portability gate**

```powershell
git add .github/workflows/v2-plugin-smoke.yml packages/router-core/tests/plugin/test_plugin_layout.py plugins/workflow-skill-router/mcp/server.bundle.mjs plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "ci(plugin): verify v2 runtime on three platforms"
```

## Final Verification

- [ ] Plugin-creator validator passes against `plugins/workflow-skill-router` with no unsupported manifest fields or missing references.
- [ ] `npm ls` proves SDK `1.29.0`、zod `4.1.12`、esbuild `0.28.1`; `package-lock.json` is committed.
- [ ] MCP `listTools` returns exactly the ten names in Public Tool Contract and no raw append／host Goal mutation tool.
- [ ] Multiple MCP calls use one Python child; bridge crash rejects pending calls and does not silently retry side effects.
- [ ] Windows `py -3.11`／`python` and POSIX `python3`／`python` discovery paths all have tests; Python 3.10 fails closed.
- [ ] Missing Python exits 78 with `skill-only-fallback`, while `skills/workflow-skill-router/SKILL.md` remains valid and usable.
- [ ] Node adapter contains transport/discovery only; routing、consent、state、Goal and evaluation policy remain in Python core or the semantic fallback SKILL.
- [ ] `.pyz` and MCP bundle regenerate deterministically and committed hashes match.
- [ ] V2 CLI tests do not import or reinterpret any V1 script; existing V1 suite still passes.
- [ ] Three-OS workflow exercises UTF-8、SQLite、MCP stdio、CLI、fallback and deterministic builds.

## Self-Review Result

- Spec coverage: official scaffold、manifest、ten tools、persistent bridge、stable dependency pins、CLI、Goal-safe service handoff、fallback disclosure、deterministic artifacts and three-OS strategy each have a focused red/green task.
- Interface consistency: bridge calls the exact `RouterService` methods defined by plans 03/05; state imports use the shared `workflow_skill_router.workflow` layer and no second policy engine appears in Node.
- Packaging boundary: repository Plugin is created without marketplace changes; installation/reinstall remains a separate explicitly authorized workflow.
