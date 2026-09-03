# Adaptive Workflow Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以預設關閉、Local-first、可清除、可審核及可回滾的方式，為 Workflow Skill Router 加入 Workflow Memory、History Analytics、Reviewed Profile Promotion 與 Automatic Managed Memory。

**Architecture:** 新增獨立的 `workflow_skill_router.memory` bounded context，將 Memory Policy、Optional History Store、Observation、Analytics、Candidate、Profile Proposal 與 Revision 與既有 Routing／Operational Event Store 分離。核心先完成 deterministic、CLI-visible 的本機能力，再一次性接入 typed MCP surface；任何記憶結果仍只代表 `intended-unverified` route，不取得 Skill activation、Runtime、Side Effect 或 Native Goal authority。

**Tech Stack:** Python 3.11+ standard library、SQLite、JSON Schema Draft 2020-12、TypeScript、Node.js 24+、Zod、Model Context Protocol、Astro/Starlight、`unittest`、Node test runner、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-09-03-adaptive-workflow-memory-design.md`

## Global Constraints

- 沒有有效 Personal Memory Policy 時，Effective Mode 必須是 `disabled`，不得建立 Memory DB、Observation、Candidate、Managed Profile 或 Remember Prompt。
- Autonomy order 固定為 `disabled < observe < reviewed < automatic`；Workspace Policy 只能降低 Personal Ceiling，不能自行開啟或提高記憶能力。
- Memory Policy 固定放在 Personal Data Root 的 `config/workflow-memory.{json,yaml,yml}` 或可信任 Workspace Root 的 `.codex/workflow-memory.{json,yaml,yml}`；不得接受模型提供的任意路徑。
- 同一 Scope 同時存在兩種以上格式時，回傳 `ambiguous-memory-policy` 並停用該 Scope 的記憶；不得依檔名排序選一份。
- Python Core 維持零 Runtime dependency。YAML 使用本計畫定義的 restricted YAML 1.2 parser，不加入 PyYAML 或其他可執行型別 Loader。
- Memory Policy 檔案必須是 UTF-8、Regular Non-link File、最大 64 KiB；YAML 禁止 Anchor、Alias、Merge Key、Tag、多文件、Duplicate Key、Tab indentation、Block Scalar 與 Flow Collection。
- Canonical JSON 是唯一 Digest 表示；語意等價的 JSON 與 YAML 必須得到相同 `sha256:` Digest。
- 預設永久禁止保存 Raw Prompt、完整 Objective、Absolute Path、File Content、Tool Arguments、Secrets 與 Skill Instruction Body；Objective 與 Workspace Identity 只允許 Digest 或 `never`。
- Optional Memory History 使用獨立 SQLite Store，支援 Retention 與 Purge；不得把可選學習歷史只寫入既有 append-only `workflow_events`。
- 已發布的 Operational Migration 不得修改；Memory Store 使用自己的 append-only migration package與 checksum。
- `workflow-skill-router/routing-profile@1.0.0` 不加入 History、Confidence、Retention 或 Memory 欄位。
- User-owned Personal／Workspace Profile 不得被 Automatic Mode 寫入。Automatic Mode 只能寫 Router-managed Personal 或 Router-managed Workspace-local Profile。
- 每次 Router-mediated Profile Write 必須完成 Strict Decode、Profile Lint、Conflict Check、Backtest、Expected Digest、Compare-and-Swap、Atomic Replace、Post-write Validation 與 Profile Revision。
- Rollback 以目前版本為基準建立新的 Forward Revision；不得刪除或改寫既有 Revision。
- User explicit Skill Lock 永遠優先；Rejected Support Skill 不得因 Memory Candidate 被重新加入當次 route。
- Remembered Skill Tree 仍是 `intended-unverified`；Memory 不安裝 Skill／Plugin、不啟用 Instructions、不授權 Filesystem／Network／Subprocess／Secrets、不授權 Deployment／Publication／Production，也不修改 Native Codex Goal。
- 第一版只使用 deterministic route signatures、thresholds、pattern mining 與 backtest；不加入 Embedding 或 LLM direct persistence。
- Default CI 不呼叫 Live Model、不消耗 Provider Quota，也不把 Fixture 宣稱為 Model Evidence。
- 每個垂直切片必須從前一切片合併後的最新 `main` 建立獨立 Branch 與 Draft PR；使用者核准前不得轉 Ready 或 Merge。
- 每個 Draft PR 必須在 exact pushed head 上完成 Focused Tests、Core Gate、Plugin Gate 及適用的 Site Gate；head 改變後重新跑 Gate。
- 合併採 Squash Merge；合併後必須確認 `main` 的 push-triggered CI，而不是只依賴 PR Check。

---

## 1. Delivery Topology

本功能分成十個可獨立審查的垂直切片。每個切片完成可執行、可測試的成果，不在同一 PR 混合兩個不同 Authority Boundary。

| Slice | Branch | Deliverable | Depends on |
| --- | --- | --- | --- |
| S0 | `codex/adaptive-workflow-memory-spec` | 已核准規格、ADR、設定範例與本計畫 | none |
| M0-A | `codex/memory-m0-policy-contract` | Memory Policy Contract、restricted YAML、Canonical Digest | S0 merged |
| M0-B | `codex/memory-m0-policy-resolution` | Fixed-location Loader、Personal/Workspace Resolver、CLI status/validate/explain | M0-A |
| M1-A | `codex/memory-m1-store` | Default-off Optional Memory Store 與獨立 Migrations | M0-B |
| M1-B | `codex/memory-m1-observations` | Completed Workflow Reader、Eligibility、Sanitized Observation、Remember command | M1-A |
| M1-C | `codex/memory-m1-analytics` | Typed Feedback、History Summary、Retention、Export、Purge | M1-B |
| M2-A | `codex/memory-m2-candidates` | Deterministic Pattern Mining、Candidate Gate、Suppression | M1-C |
| M2-B | `codex/memory-m2-profile-proposals` | Profile Diff、Backtest、Proposal State Machine | M2-A |
| M2-C | `codex/memory-m2-revisions` | CAS、Atomic Materializer、Revision、Reviewed Write、Rollback | M2-B |
| M3-A | `codex/memory-m3-managed-profiles` | Managed Profile Storage 與固定 Layer Precedence | M2-C |
| M3-B | `codex/memory-m3-automatic-promotion` | Automatic Managed Promotion、Conflict Suppression、Notifications | M3-A |
| M4-A | `codex/memory-m4-mcp-surface` | 8 個 Typed MCP Memory Tools、Runtime Readiness、Generated Reference | M3-B |
| M4-B | `codex/memory-m4-docs-flight-recorder` | 中英文文件、設定範例封裝、Flight Recorder、Migration/Pilot Guide | M4-A |

### 每個 Slice 的固定交付流程

1. 使用 `superpowers:using-git-worktrees` 從最新 `main` 建立隔離 Worktree。
2. 建立上表指定 Branch，立刻 Push 並開 Draft PR。
3. 先寫失敗測試，再寫最小實作；每個行為群組使用獨立 Commit。
4. 執行 Slice Focused Tests，再執行 Repository Gate。
5. 比對本機 SHA、Remote Branch SHA 與 PR Head SHA；三者必須一致。
6. 等待所有 Required Checks 對 exact head 結束；不得以較舊 SHA 的綠燈取代。
7. 回報 User-visible Contract、Diff、Proof 與 Remaining Limits，等待使用者核准。
8. 核准後轉 Ready、Squash Merge、刪除遠端 Branch。
9. 讀取 `main` 新 Merge SHA，確認 push-triggered CI。
10. 下一 Slice 只能從此 `main` SHA 建立。

---

## 2. Target File Structure

新增模組依責任拆分，避免把 Memory 子系統塞進既有大型 `local_control.py`。

```text
packages/router-core/src/workflow_skill_router/
  memory/
    __init__.py                 # Public internal interfaces only
    models.py                   # Shared enums and immutable result models
    policy.py                   # Strict Memory Policy contract and presets
    safe_yaml.py                # Restricted YAML 1.2 parser
    policy_io.py                # Fixed-location JSON/YAML loading
    policy_resolver.py          # Personal ceiling + Workspace restriction
    store.py                    # Optional SQLite store and transactions
    migrator.py                 # Memory-only migration runner
    migrations/
      __init__.py
      0001_observations.sql
      0002_candidates.sql
      0003_profile_changes.sql
    workflow_reader.py          # Read-only projection from Router operational DB
    observations.py             # Eligibility, redaction, route signatures
    feedback.py                 # Typed feedback transitions
    analytics.py                # Deterministic summaries and retention
    candidates.py               # Pattern mining and promotion thresholds
    backtest.py                 # Profile conflict and historical backtest
    profile_diff.py             # Semantic + canonical JSON diff
    proposals.py                # Bound proposal state machine
    revisions.py                # Revision metadata and snapshots
    materializer.py             # CAS + atomic fixed-target writes
    managed_profiles.py         # Managed Personal/Workspace-local storage
    service.py                  # Thin Memory control-plane orchestration
  cli/
    memory.py                   # CLI surface by milestone
```

既有檔案只負責接線：

- `local_control.py`：建立一次 `MemoryService` 並委派 typed operation；不包含 Policy／Analytics／Promotion 實作。
- `profiles/storage.py`：共用安全 fixed-path read/write primitives，並載入 Managed Profile layers。
- `profiles/resolver.py`：新增明確的 Profile Layer rank，不用 priority 模擬 Owner precedence。
- `service_models.py`、`service_codecs.py`、`tool_dispatch.py`、`runtime_readiness.py`：M4-A 才公開 MCP Memory contracts。
- TypeScript MCP files：M4-A 一次性新增完整 public surface，避免每個 Core Slice 改動工具數量。

---

### Task 1: M0-A — Memory Policy Contract 與 Restricted YAML Codec

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/policy.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/safe_yaml.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/memory-policy.schema.json`
- Create: `packages/router-core/tests/memory/__init__.py`
- Create: `packages/router-core/tests/memory/test_policy_contract.py`
- Create: `packages/router-core/tests/memory/test_safe_yaml.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- Produces: `MemoryMode`, `MemoryScope`, `MemoryPolicy`, `MemoryPolicyError`.
- Produces: `decode_memory_policy(document: Mapping[str, object], *, expected_scope: MemoryScope | None = None) -> MemoryPolicy`.
- Produces: `memory_policy_document(policy: MemoryPolicy) -> dict[str, object]`.
- Produces: `parse_safe_yaml(text: str) -> Mapping[str, object]`.
- Produces: `decode_policy_text(text: str, *, format: Literal["json", "yaml"], expected_scope: MemoryScope | None = None) -> MemoryPolicy`.
- Later tasks consume `MemoryPolicy.policy_digest`, `MemoryPolicy.mode`, and normalized preset sections.

- [ ] **Step 1: Write the failing schema inventory test**

Update the schema count from five to six and assert the Memory Policy schema identity and closed object shape:

```python
def test_memory_policy_schema_is_strict_and_default_off_capable(self) -> None:
    document = json.loads(
        (SCHEMA_ROOT / "memory-policy.schema.json").read_text(encoding="utf-8")
    )
    self.assertEqual("workflow-skill-router/memory-policy", document["properties"]["schema_id"]["const"])
    self.assertEqual(False, document["additionalProperties"])
    self.assertEqual(["disabled", "observe", "reviewed", "automatic"], document["properties"]["mode"]["enum"])
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest packages.router-core.tests.schemas.test_schema_documents -v
```

Expected: FAIL because `memory-policy.schema.json` does not exist and the document count is still five.

- [ ] **Step 3: Add the strict JSON Schema**

The schema must require only:

```json
{
  "schema_id": "workflow-skill-router/memory-policy",
  "schema_version": "1.0.0",
  "artifact_kind": "memory-policy",
  "policy_id": "personal:default",
  "scope": "personal",
  "mode": "disabled"
}
```

Optional sections are `storage`, `privacy`, `eligibility`, `features`, and `notifications`. Every object uses `additionalProperties: false`; automatic thresholds have equal or stronger JSON Schema bounds than reviewed thresholds where static validation can express them.

- [ ] **Step 4: Write failing Python contract tests**

Cover exact fields, mode presets, scope agreement, threshold ordering, forbidden privacy values, unknown fields, duplicate list values, and deterministic digest:

```python
def test_minimal_personal_policy_decodes_to_disabled_preset(self) -> None:
    policy = decode_memory_policy(minimal_policy("disabled"), expected_scope=MemoryScope.PERSONAL)
    self.assertEqual(MemoryMode.DISABLED, policy.mode)
    self.assertEqual("none", policy.capture)
    self.assertEqual("disabled", policy.features.remember_this_workflow.mode)
    self.assertRegex(policy.policy_digest, r"^sha256:[0-9a-f]{64}$")


def test_automatic_thresholds_cannot_be_weaker_than_reviewed(self) -> None:
    document = full_policy("automatic")
    document["eligibility"]["minimum_distinct_runs_automatic"] = 2
    with self.assertRaisesRegex(MemoryPolicyError, "automatic-threshold-weaker"):
        decode_memory_policy(document)
```

- [ ] **Step 5: Run contract tests and verify they fail**

Run:

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_contract.py" -v
```

Expected: FAIL with import errors for the new contract.

- [ ] **Step 6: Implement immutable contract models and presets**

Use string enums and frozen dataclasses. `decode_memory_policy` must reject any unknown or missing required field, normalize omitted optional sections from the selected mode preset, validate cross-field constraints, then compute:

```python
policy_digest = "sha256:" + hashlib.sha256(
    canonical_json(memory_policy_document(policy_without_digest)).encode("utf-8")
).hexdigest()
```

Do not include source path, file format, or comments in the digest.

- [ ] **Step 7: Write failing restricted YAML tests**

The accepted subset is block mapping/list syntax with two-space indentation, JSON-compatible scalars, full-line comments, plain strings, and JSON double-quoted strings. Reject unsafe or ambiguous syntax:

```python
UNSAFE = (
    "defaults: &defaults\n  mode: automatic\npolicy:\n  <<: *defaults\n",
    "mode: !!python/object:example\n",
    "---\nmode: disabled\n---\nmode: automatic\n",
    "mode: disabled\nmode: automatic\n",
    "features:\n\tremember_this_workflow:\n",
    "text: |\n  hidden\n",
    "features: {mode: automatic}\n",
)


def test_rejects_unsafe_yaml(self) -> None:
    for text in UNSAFE:
        with self.subTest(text=text):
            with self.assertRaises(MemoryPolicyError):
                parse_safe_yaml(text)
```

- [ ] **Step 8: Implement the zero-dependency YAML parser**

`safe_yaml.py` must:

1. Normalize `\r\n` to `\n` and reject NUL/BOM.
2. Ignore blank lines and full-line comments only.
3. Require spaces in multiples of two and reject tabs.
4. Parse block mappings and `-` sequences with a stack of `(indent, container)` frames.
5. Reject duplicate keys before inserting.
6. Parse only `null`, `true`, `false`, base-10 integers, finite decimals, JSON double-quoted strings, and restricted plain strings.
7. Reject tokens containing YAML control syntax `& * ! << | > { } [ ]` outside a JSON double-quoted scalar.
8. Return only `dict[str, object]`, `list[object]`, `str`, `int`, `float`, `bool`, or `None`.

- [ ] **Step 9: Lock JSON/YAML canonical parity**

Add a test loading `docs/architecture/examples/workflow-memory.reviewed.yaml` and an equivalent JSON document, then assert equal normalized documents and equal digests. Also assert comments and key order do not affect the digest.

- [ ] **Step 10: Run focused and package tests**

Run:

```powershell
python -m unittest discover -s packages/router-core/tests/memory -v
python -m unittest packages.router-core.tests.schemas.test_schema_documents -v
python plugins/workflow-skill-router/scripts/build-runtime.py --check
```

Expected: all Memory Policy tests pass; runtime check initially reports archive drift until the tracked bundle is regenerated by the established build workflow.

- [ ] **Step 11: Regenerate the bundled Python runtime and verify determinism**

Run:

```powershell
python plugins/workflow-skill-router/scripts/build-runtime.py
python plugins/workflow-skill-router/scripts/build-runtime.py --check
```

Expected: second command exits `0`.

- [ ] **Step 12: Commit M0-A in focused commits**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/schemas/json/v2/memory-policy.schema.json packages/router-core/tests/memory packages/router-core/tests/schemas/test_schema_documents.py
git commit -m "feat(memory): define strict memory policy contract"
git add plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "build(plugin): bundle memory policy contract"
```

---

### Task 2: M0-B — Fixed-location Policy Loader、Effective Resolver 與 CLI

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/policy_io.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/policy_resolver.py`
- Create: `packages/router-core/src/workflow_skill_router/cli/memory.py`
- Create: `packages/router-core/tests/memory/test_policy_io.py`
- Create: `packages/router-core/tests/memory/test_policy_resolver.py`
- Create: `packages/router-core/tests/cli/test_memory_cli.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/__init__.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/__init__.py`

**Interfaces:**
- Produces: `PolicySource(scope, format, source_class, policy, warnings)` without exposing full path in public output.
- Produces: `EffectiveMemoryPolicy(mode, personal_mode, workspace_requested_mode, policy_source, policy_digest, capture_enabled, candidate_generation_enabled, profile_promotion, allowed_targets, reason_codes)`.
- Produces: `MemoryPolicyRepository(data_dir: Path).load_personal()` and `.load_workspace(workspace_root: Path)`.
- Produces: `resolve_effective_policy(*, personal: PolicySource | None, workspace: PolicySource | None, host_disabled: bool = False, explicit_no_memory: bool = False) -> EffectiveMemoryPolicy`.
- Produces CLI commands `memory status`, `memory policy validate`, and `memory policy explain`.

- [ ] **Step 1: Write failing fixed-location tests**

Cover `.json`, `.yaml`, `.yml`, multiple-format ambiguity, non-link files, 64 KiB limit, invalid UTF-8, and no directory creation during read:

```python
def test_missing_personal_policy_does_not_create_data_root(self) -> None:
    data_dir = self.root / "missing"
    source = MemoryPolicyRepository(data_dir).load_personal()
    self.assertIsNone(source)
    self.assertFalse(data_dir.exists())


def test_multiple_personal_formats_fail_closed(self) -> None:
    self.write("config/workflow-memory.json", json.dumps(minimal_policy("observe")))
    self.write("config/workflow-memory.yaml", yaml_policy("reviewed"))
    with self.assertRaisesRegex(MemoryPolicyError, "ambiguous-memory-policy"):
        MemoryPolicyRepository(self.root).load_personal()
```

- [ ] **Step 2: Implement safe source discovery**

At each Scope, collect only the three fixed candidate names. Resolve the source relative to the approved root, reject symlink/reparse points, validate size before reading, parse using the extension-specific codec, and return sanitized reason codes. Do not include the absolute path in `PolicySource.to_public_dict()`.

- [ ] **Step 3: Write failing resolution tests**

```python
def test_workspace_cannot_elevate_personal_ceiling(self) -> None:
    effective = resolve_effective_policy(
        personal=source("personal", "observe"),
        workspace=source("workspace", "automatic"),
    )
    self.assertEqual(MemoryMode.OBSERVE, effective.mode)
    self.assertIn("workspace-policy-exceeds-ceiling", effective.reason_codes)


def test_invalid_workspace_policy_disables_memory_for_that_workspace(self) -> None:
    effective = resolve_effective_policy(
        personal=source("personal", "automatic"),
        workspace=invalid_source("workspace"),
    )
    self.assertEqual(MemoryMode.DISABLED, effective.mode)
    self.assertEqual("invalid-workspace-policy", effective.policy_source)
```

- [ ] **Step 4: Implement deterministic policy intersection**

Resolve in this order:

```text
host hard disable
-> explicit no-memory
-> Personal Policy ceiling
-> Workspace restriction
-> feature autonomy intersection
-> stricter numeric limits
-> target set intersection
-> stricter privacy representation
```

Use the larger value for minimum evidence thresholds, smaller value for maximum rates/retention/counts, and set intersection for targets. Canonicalize the effective public-safe snapshot to compute the Effective Policy Digest.

- [ ] **Step 5: Write failing CLI tests**

Assert JSON-only stdout, stable exit codes, no full local path, and default-off status:

```python
def test_memory_status_is_disabled_without_policy(self) -> None:
    result = run_cli(["memory", "status"], data_dir=self.root)
    self.assertEqual(0, result.code)
    payload = json.loads(result.stdout)
    self.assertEqual("disabled", payload["mode"])
    self.assertEqual("personal-policy-missing", payload["reason_codes"][0])
    self.assertFalse((self.root / "memory/workflow-memory.sqlite3").exists())
```

- [ ] **Step 6: Implement CLI parser and commands**

Command contracts:

```text
workflow-skill-router memory status [--workspace <trusted-user-path>]
workflow-skill-router memory policy validate <file> --scope personal|workspace
workflow-skill-router memory policy explain [--workspace <trusted-user-path>]
```

`validate` may read the explicit CLI file because the local human invoked the CLI; MCP never reuses this arbitrary-path command. `status` and `explain` only read fixed policy locations.

- [ ] **Step 7: Run focused tests and runtime checks**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_*.py" -v
python -m unittest packages.router-core.tests.cli.test_memory_cli -v
python plugins/workflow-skill-router/scripts/build-runtime.py
python plugins/workflow-skill-router/scripts/build-runtime.py --check
```

- [ ] **Step 8: Commit M0-B**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli packages/router-core/tests/memory packages/router-core/tests/cli/test_memory_cli.py
git commit -m "feat(memory): resolve default-off memory policies"
git add plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "build(plugin): bundle memory policy resolution"
```

---

### Task 3: M1-A — Optional Memory Store 與獨立 Migration Boundary

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrator.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0001_observations.sql`
- Create: `packages/router-core/tests/memory/test_memory_migrator.py`
- Create: `packages/router-core/tests/memory/test_memory_store.py`

**Interfaces:**
- Produces: `memory_database_path(data_dir: Path) -> Path` fixed to `memory/workflow-memory.sqlite3`.
- Produces: `MemoryStore.open_if_enabled(data_dir: Path, policy: EffectiveMemoryPolicy) -> MemoryStore | None`.
- Produces: `MemoryStore.transaction()` and typed insert/read methods; callers do not receive raw writable SQLite connections.
- Produces: `migrate_memory_store(database: Path) -> None` with its own `memory_schema_migrations` checksums.

- [ ] **Step 1: Write the failing default-off storage test**

```python
def test_disabled_policy_never_creates_memory_directory_or_database(self) -> None:
    store = MemoryStore.open_if_enabled(self.data_dir, disabled_policy())
    self.assertIsNone(store)
    self.assertFalse((self.data_dir / "memory").exists())
```

- [ ] **Step 2: Write failing migration tests**

Assert enabled open creates only the separate Memory DB; repeat migration is idempotent; modified migration checksum fails; operational `router-v2.sqlite3` is untouched.

- [ ] **Step 3: Add the first Memory Store migration**

`0001_observations.sql` creates:

```sql
CREATE TABLE memory_schema_migrations (...);
CREATE TABLE memory_command_receipts (...);
CREATE TABLE memory_policy_snapshots (...);
CREATE TABLE route_observations (...);
CREATE TABLE route_feedback (...);
CREATE INDEX idx_route_observations_signature_time
  ON route_observations(route_signature_digest, observed_at);
```

Use strict `CHECK` constraints for modes, eligibility status, feedback type, and `profile_source_class`. `route_observations` stores only canonical JSON payloads with digests; no plaintext objective or path column exists.

- [ ] **Step 4: Implement Memory-only migrator**

Mirror the repository checksum and transaction behavior without importing or scanning `persistence.migrations`. Memory migration version keys use their filename prefix inside `memory_schema_migrations` only.

- [ ] **Step 5: Implement lazy store opening**

`open_if_enabled` returns `None` before touching the filesystem when `policy.capture_enabled` is false. For enabled modes, create `memory/`, reject symlink/reparse boundaries, migrate, enable foreign keys and WAL, and expose bounded repository methods.

- [ ] **Step 6: Add corruption and permission tests**

Cover Memory DB path as directory, symlinked `memory/`, checksum drift, non-database content, and transaction rollback. Public errors return `memory-store-unavailable` or `memory-store-corrupt` without leaking full paths.

- [ ] **Step 7: Run M1-A tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_memory_migrator -v
python -m unittest packages.router-core.tests.memory.test_memory_store -v
python -m unittest discover -s packages/router-core/tests/persistence -v
```

- [ ] **Step 8: Commit M1-A**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/tests/memory
git commit -m "feat(memory): add optional purgeable memory store"
```

---

### Task 4: M1-B — Completed Workflow Reader、Eligibility 與 Route Observation

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/workflow_reader.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/observations.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Create: `packages/router-core/tests/memory/test_workflow_reader.py`
- Create: `packages/router-core/tests/memory/test_observations.py`
- Create: `packages/router-core/tests/memory/test_remember_workflow.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`

**Interfaces:**
- Produces: `MatcherSeed(objective_keywords, domains, tags, source)`; allowed sources are `trusted-routing-context`, `existing-profile`, and `user-explicit`.
- Produces: `CompletedWorkflowSnapshot` from read-only Operational DB queries.
- Produces: `RememberWorkflowCommand(context, workflow_run_id, workspace_root, matcher_seed, target_profile_class, risk_class, side_effect_outcome, one_shot, idempotency_key, correlation_id)`.
- Produces: `MemoryService.remember_workflow(command) -> RememberWorkflowResult`.
- `RememberWorkflowResult` includes nullable `observation_id`, signature digest, eligibility status/reasons, nullable candidate ID, target, approval requirement, write status, policy digest, and `authority_mode="router-local"`.

- [ ] **Step 1: Write failing Operational Workflow Reader tests**

Use `LocalControlPlaneService` fixtures to create Single and Phased plans. Assert the reader binds session, actor, and Runtime Policy Snapshot; reads plan/phase/transition structure; and refuses incomplete, cross-session, corrupt, or Native Goal-owned records.

- [ ] **Step 2: Implement read-only workflow projection**

Read `local_control_plans`, ordered `local_work_items`, and ordered `local_work_transitions.observation_json`. A completed local snapshot requires every required item to be `completed` and every terminal phase to have a matching persisted `local-gate` with `passed=true`. Do not return `reported_outcome` free text to the Memory layer.

- [ ] **Step 3: Write failing signature and privacy tests**

```python
def test_route_signature_contains_structure_not_objective_or_paths(self) -> None:
    signature = build_route_signature(completed_snapshot(), matcher_seed())
    document = signature.to_dict()
    serialized = canonical_json(document)
    self.assertNotIn("Create the student API", serialized)
    self.assertNotIn(str(self.workspace), serialized)
    self.assertEqual("phased", document["envelope"])
    self.assertRegex(signature.digest, r"^sha256:[0-9a-f]{64}$")
```

- [ ] **Step 4: Implement eligibility and normalization**

Eligibility requires terminal success, required gate pass, known side-effect outcome `none` or `known-success`, no explicit `no-memory`, canonical Skill IDs, non-R3 risk, no pending consent, and at least one Matcher Seed signal. A route from `user-explicit` is eligible only in `reviewed` mode or an explicit `remember-once`; it is never automatically promotable.

- [ ] **Step 5: Define the Matcher Seed rule**

Candidate matching material may come only from:

1. trusted `domains`/`tags` supplied by a verified routing context;
2. the matcher of the already matched Routing Profile;
3. an explicit structured `MatcherSeed` supplied when the user chooses Remember This Workflow.

Do not derive or store keywords from Raw Objective. If all three sources are empty, return `insufficient-match-signal` and do not persist an Observation.

- [ ] **Step 6: Write failing remember/idempotency tests**

Cover disabled policy, observe policy, explicit no-memory, unknown side effect, incomplete workflow, duplicate Resume, same idempotency key/same request, same idempotency key/different request, and sanitized stored payload.

- [ ] **Step 7: Implement `MemoryService.remember_workflow`**

Flow:

```text
resolve current effective policy
-> stop before Store open when disabled/no-memory
-> read and validate completed workflow
-> normalize Matcher Seed
-> evaluate eligibility
-> open Store only when capture is allowed
-> upsert effective policy snapshot
-> replay command receipt or insert one Observation
-> return public-safe result
```

A Memory failure must not mutate the Operational Router DB. CLI errors are non-zero only because Memory is the primary command; future routing hooks report memory disabled and continue routing.

- [ ] **Step 8: Add CLI `memory remember`**

```text
workflow-skill-router memory remember \
  --database <router-v2.sqlite3> \
  --workflow-run <id> \
  --domain api \
  --target managed-personal \
  --risk r0 \
  --side-effect none
```

CLI accepts repeated `--keyword`, `--domain`, and `--tag`; it never accepts a Profile target path.

- [ ] **Step 9: Run M1-B tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_workflow_reader -v
python -m unittest packages.router-core.tests.memory.test_observations -v
python -m unittest packages.router-core.tests.memory.test_remember_workflow -v
python -m unittest packages.router-core.tests.integration.test_local_work_loop -v
```

- [ ] **Step 10: Commit M1-B**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/memory
git commit -m "feat(memory): capture eligible workflow observations"
```

---

### Task 5: M1-C — Typed Feedback、History Analytics、Retention、Export 與 Purge

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/feedback.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/analytics.py`
- Create: `packages/router-core/tests/memory/test_route_feedback.py`
- Create: `packages/router-core/tests/memory/test_history_analytics.py`
- Create: `packages/router-core/tests/memory/test_retention_and_purge.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`

**Interfaces:**
- Produces: `RecordRouteFeedbackCommand` with enum feedback type and standard reason code.
- Produces: `HistorySummaryQuery` and `HistorySummary`.
- Produces: `PurgeMemoryCommand(scope, expected_summary_digest, include_managed_profiles, idempotency_key)`.
- Produces: `MemoryService.record_route_feedback`, `.history_summary`, `.export_history`, and `.purge_memory`.

- [ ] **Step 1: Write failing feedback contract tests**

Allowed types are `accepted`, `corrected`, `rejected`, `support-rejected`, `capability-unavailable`, `gate-failed`, `completed`, `abandoned`, and `no-memory`. `corrected` requires original/corrected signature digests and at least one correction dimension. Free text is rejected unless Policy explicitly allows it; it never enters matcher generation.

- [ ] **Step 2: Implement typed feedback transitions**

Bind Feedback to an existing Observation and current Policy Digest. Enforce idempotency receipts and reject cross-observation signature replacement. Store only reason codes and structured dimensions.

- [ ] **Step 3: Write failing analytics tests**

Use fixture observations across duplicate Resume, dates, workspaces, outcomes, consent rejection, and corrections. Assert metrics are calculated by distinct `workflow_run_id`:

```python
self.assertEqual(5, summary.eligible_workflow_count)
self.assertEqual(0.80, summary.completion_rate)
self.assertEqual(0.20, summary.manual_correction_rate)
self.assertEqual("medium", summary.confidence)
```

- [ ] **Step 4: Implement deterministic analytics**

Return counts and ratios for Route frequency, completion, gate pass, correction, consent rejection, capability unavailable, planned/actual consistency class, distinct active days, Workspace distribution, Profile source distribution, and Candidate acceptance when tables become available. Confidence categories use exact threshold rules; do not output model-like probability.

- [ ] **Step 5: Write failing Retention/Purge tests**

Assert:

- Observation age and maximum count limits are enforced deterministically.
- Candidate/revision tables not yet present do not break M1 cleanup.
- Disabled mode does not implicitly purge.
- `purge_on_disable` deletes Optional History only after effective-policy transition processing.
- Purge requires an exact pre-operation Summary Digest.
- `all-memory-data` does not delete User-owned Profiles.

- [ ] **Step 6: Implement retention and explicit purge**

Purge scopes are `history-only`, `analytics-only`, `candidates-only`, `revisions-only`, `managed-profiles-only`, and `all-memory-data`. M1 implements the first two and returns `scope-not-available` for future scopes without deleting unrelated data. Use one transaction and a command receipt.

- [ ] **Step 7: Implement redacted export**

Export canonical JSON containing aggregate metrics and optional sanitized Observation structures. Reject exports containing objective/path/tool-argument keys, and scan serialized output for the Router Data Root before writing.

- [ ] **Step 8: Extend CLI**

```text
workflow-skill-router memory feedback record ...
workflow-skill-router memory history summary
workflow-skill-router memory history export --output <reviewed-file>
workflow-skill-router memory history purge --scope history-only --expected-summary-digest sha256:...
```

- [ ] **Step 9: Run M1-C tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_route_feedback -v
python -m unittest packages.router-core.tests.memory.test_history_analytics -v
python -m unittest packages.router-core.tests.memory.test_retention_and_purge -v
```

- [ ] **Step 10: Commit M1-C**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/memory
git commit -m "feat(memory): add route feedback and history analytics"
```

---

### Task 6: M2-A — Deterministic Pattern Mining、Workflow Candidate 與 Suppression

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0002_candidates.sql`
- Create: `packages/router-core/src/workflow_skill_router/memory/candidates.py`
- Create: `packages/router-core/tests/memory/test_candidate_migration.py`
- Create: `packages/router-core/tests/memory/test_candidate_engine.py`
- Create: `packages/router-core/tests/memory/test_candidate_suppression.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`

**Interfaces:**
- Produces: `PatternMetrics`, `WorkflowPattern`, `WorkflowCandidate`, and `CandidateDecision`.
- Produces: `CandidateEngine.rebuild(scope: MemoryScope, now: datetime) -> tuple[WorkflowCandidate, ...]`.
- Produces: `candidate_digest` from matcher, route, evidence summary, target class, and engine revision.
- Produces: Candidate states `proposed`, `rejected`, `expired`, `suppressed`, `superseded`, and later `approved`/`auto-promoted`.

- [ ] **Step 1: Add candidate tables with a failing migration test**

`0002_candidates.sql` creates `workflow_patterns`, `workflow_candidates`, and `candidate_suppressions`. Candidate status, confidence, mode eligibility, target class, material evidence digest, and timestamps use constrained columns.

- [ ] **Step 2: Write failing grouping tests**

Observations group by Scope, normalized Matcher Seed, Envelope, Phase/Skill/Gate sequence, Workspace Digest for workspace-local targets, and Profile Source Class. Same route with a different matcher or workspace does not merge.

- [ ] **Step 3: Implement deterministic metrics**

Compute distinct runs/days, completion rate, required gate pass rate, manual correction rate, route consistency, canonical Skill identity status, hard contract violations, and evidence digest from sorted Observation IDs/Digests.

- [ ] **Step 4: Write reviewed/automatic threshold tests**

Reviewed defaults: 3 runs, 2 days, success/gate `>=0.80`, correction `<=0.20`, consistency `>=0.75`, zero hard violation.

Automatic defaults: 5 runs, 3 days, success/gate `>=0.90`, correction `<=0.10`, consistency `>=0.85`, canonical Skill IDs, zero hard violation, managed target only.

Automatic thresholds can be stricter in Policy but never weaker than reviewed.

- [ ] **Step 5: Enforce non-promotable cases**

Return `insufficient-evidence`, `insufficient-match-signal`, `explicit-route-requires-review`, `unknown-skill-identity`, `hard-contract-violation`, or `target-not-managed` rather than creating an automatic Candidate.

- [ ] **Step 6: Write suppression tests**

A rejected Candidate with unchanged `material_evidence_digest` is suppressed until the configured date. New distinct successful evidence changes the digest and permits a new Candidate. Candidate ID changes only when material content changes.

- [ ] **Step 7: Implement Candidate listing CLI**

```text
workflow-skill-router memory candidates rebuild
workflow-skill-router memory candidates list [--status proposed]
workflow-skill-router memory candidates show <candidate-id>
workflow-skill-router memory candidates reject <candidate-id> --reason not-reusable
```

- [ ] **Step 8: Run M2-A tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_candidate_migration -v
python -m unittest packages.router-core.tests.memory.test_candidate_engine -v
python -m unittest packages.router-core.tests.memory.test_candidate_suppression -v
```

- [ ] **Step 9: Commit M2-A**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/memory
git commit -m "feat(memory): recommend deterministic workflow candidates"
```

---

### Task 7: M2-B — Profile Diff、Historical Backtest 與 Bound Proposal State Machine

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0003_profile_changes.sql`
- Create: `packages/router-core/src/workflow_skill_router/memory/profile_diff.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/backtest.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/proposals.py`
- Create: `packages/router-core/tests/memory/test_profile_diff.py`
- Create: `packages/router-core/tests/memory/test_profile_backtest.py`
- Create: `packages/router-core/tests/memory/test_profile_proposals.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`

**Interfaces:**
- Produces: `SemanticProfileDiff`, `JsonPatchOperation`, `BacktestSummary`, `ProfileUpdateProposal`.
- Produces: `build_profile_document(candidate, current_profile) -> Mapping[str, object]` using the existing strict Routing Profile contract.
- Produces: `diff_profiles(before, after) -> SemanticProfileDiff`.
- Produces: `backtest_profile_update(current_layers, proposed_profile, observations) -> BacktestSummary`.
- Produces: `create_profile_update_proposal(candidate_id, target, expected_profile_digest) -> ProfileUpdateProposal`.
- Produces: `transition_profile_update(proposal_id, action, bound_revision, idempotency_key)` with actions `approve` or `reject` only.

- [ ] **Step 1: Add proposal/revision index tables**

Migration creates `profile_update_proposals` and `profile_revision_index`; snapshot files are external fixed-path artifacts, while metadata and digests live in SQLite.

- [ ] **Step 2: Write failing Semantic Diff tests**

Cover Rule add/remove/change, Matcher change, Priority, Work Mode, Phase order, Primary Skill, Support Skill, and Exit Gate. Ordering must be stable by Rule ID, Phase position, and field name.

- [ ] **Step 3: Implement Semantic + Canonical JSON Diff**

Return both human-readable typed entries and RFC 6901-style JSON pointer operations. Do not include comments, source path, or Raw Prompt.

- [ ] **Step 4: Write failing Backtest tests**

Backtest the proposed Profile against stored structured Matcher Seeds and existing user-owned Profile layers. Report Positive Match Coverage, Unexpected Match Count, Shadowed Rules, Equal-rank Conflicts, Manual Precedence, Capability Gap Summary, Planned/Actual Regression class, and Workspace Isolation.

- [ ] **Step 5: Implement Backtest using existing strict resolver semantics**

Do not invoke an LLM. Convert the Candidate to a decoded `RoutingPreferenceProfile`, use the same lexical/domain/tag/work-mode matching functions as runtime routing, and keep User-owned Profiles ahead of Candidate layers.

- [ ] **Step 6: Write failing bound proposal tests**

A transition request contains only Proposal ID, action, expected proposal state version, idempotency key, and correlation ID. It cannot replace Candidate, Target, Diff, Matcher, Profile Document, or expected Profile Digest.

- [ ] **Step 7: Implement proposal lifecycle**

Lifecycle:

```text
pending -> approved | rejected | stale | expired
```

Creating a proposal requires Candidate evidence, strict Profile decode, zero lint errors, acceptable Backtest, and allowed target. Approval records intent but does not write a Profile until M2-C.

- [ ] **Step 8: Run M2-B tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_profile_diff -v
python -m unittest packages.router-core.tests.memory.test_profile_backtest -v
python -m unittest packages.router-core.tests.memory.test_profile_proposals -v
python -m unittest packages.router-core.tests.profiles.test_resolver -v
```

- [ ] **Step 9: Commit M2-B**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/tests/memory
git commit -m "feat(memory): create reviewable profile update proposals"
```

---

### Task 8: M2-C — Profile Revision、CAS、Atomic Materializer 與 Rollback

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/profiles/atomic_io.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/revisions.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/materializer.py`
- Create: `packages/router-core/tests/profiles/test_atomic_io.py`
- Create: `packages/router-core/tests/memory/test_profile_revisions.py`
- Create: `packages/router-core/tests/memory/test_profile_materializer.py`
- Create: `packages/router-core/tests/memory/test_profile_rollback.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/storage.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/proposals.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`

**Interfaces:**
- Produces: `secure_read_json(path, root, max_bytes)` and `atomic_write_canonical_json(path, root, document, expected_digest)`.
- Produces: `ProfileTarget(target_class, profile_id, workspace_digest, fixed_path_class)`; no arbitrary path field.
- Produces: `ProfileRevisionStore.record(...)`, `.list(profile_id)`, `.load_snapshot(revision_id)`.
- Produces: `ProfileMaterializer.apply_approved(proposal, authority) -> ProfileRevision`.
- Produces: `create_rollback_proposal(profile_id, selected_revision_id, current_digest) -> ProfileUpdateProposal`.

- [ ] **Step 1: Extract and test secure profile I/O primitives**

Refactor existing Personal Profile atomic write behavior into `profiles/atomic_io.py` without changing current semantics. Tests cover fixed-root containment, regular non-link target, temp file in same directory, flush/fsync, replace, cleanup, and post-write digest validation.

- [ ] **Step 2: Write failing CAS tests**

```python
def test_changed_profile_digest_marks_proposal_stale_without_overwrite(self) -> None:
    proposal = approved_proposal(expected_profile_digest=OLD_DIGEST)
    self.write_current_profile(digest=NEW_DIGEST)
    with self.assertRaisesRegex(ProfileWriteError, "profile-drift"):
        materializer.apply_approved(proposal, local_managed_authority())
    self.assertEqual(NEW_DIGEST, self.current_digest())
    self.assertEqual("stale", self.load_proposal(proposal.id).status)
```

- [ ] **Step 3: Implement Profile Target authority matrix**

- `managed-personal`: Router-local managed authority.
- `managed-workspace-local`: deferred until M3-A, reject with `target-not-available` in this slice.
- `user-personal`: explicit reviewed approval plus local user-owned write authority.
- `workspace-file`: explicit reviewed approval plus verified Workspace Root and Host File Write Authority.

No target accepts a caller-supplied destination path.

- [ ] **Step 4: Implement revision snapshot layout**

```text
<router-data-dir>/profiles/revisions/<target-class>/<profile-id>/<revision-id>.json
```

Each Revision records previous/new digest, proposal/candidate ID, Policy Digest, actor, write authority, Semantic Diff Digest, Backtest Digest, status, and Canonical Snapshot Digest.

- [ ] **Step 5: Apply approved proposals transactionally**

Order:

```text
load bound approved proposal
-> verify expected profile digest
-> write pending revision metadata
-> atomic materialize fixed target
-> strict re-read and digest validation
-> finalize revision and proposal status
```

If filesystem write succeeds but metadata finalization fails, retain a recovery marker and reconcile by exact snapshot digest on the next call; do not blindly replay the write.

- [ ] **Step 6: Write and implement rollback tests**

Rollback selects an existing Snapshot, creates a new Proposal and Diff against current state, runs normal approval/CAS, writes the selected content, and creates a new Revision whose `status` is `rollback`. Previous revisions remain unchanged.

- [ ] **Step 7: Extend CLI review commands**

```text
workflow-skill-router memory candidates approve <candidate-id> --target managed-personal
workflow-skill-router profile revisions list <profile-id>
workflow-skill-router profile revisions diff <from-revision> <to-revision>
workflow-skill-router profile rollback <profile-id> --to <revision-id> --expected-profile-digest sha256:...
```

CLI Workspace writes are disabled in this slice; verified Host integration arrives with MCP.

- [ ] **Step 8: Run M2-C tests**

```powershell
python -m unittest packages.router-core.tests.profiles.test_atomic_io -v
python -m unittest packages.router-core.tests.memory.test_profile_revisions -v
python -m unittest packages.router-core.tests.memory.test_profile_materializer -v
python -m unittest packages.router-core.tests.memory.test_profile_rollback -v
python -m unittest discover -s packages/router-core/tests/profiles -v
```

- [ ] **Step 9: Commit M2-C**

```powershell
git add packages/router-core/src/workflow_skill_router/profiles packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/profiles packages/router-core/tests/memory
git commit -m "feat(memory): version and rollback reviewed profiles"
```

---

### Task 9: M3-A — Router-managed Profiles 與明確 Layer Precedence

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/profiles/layers.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/managed_profiles.py`
- Create: `packages/router-core/tests/profiles/test_profile_layers.py`
- Create: `packages/router-core/tests/memory/test_managed_profiles.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/storage.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/resolver.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/__init__.py`
- Modify: `packages/router-core/src/workflow_skill_router/local_control.py`
- Modify: `packages/router-core/src/workflow_skill_router/service_models.py`
- Modify: `plugins/workflow-skill-router/mcp/src/tool-output-schemas.ts`
- Modify: `packages/router-core/tests/profiles/test_resolver.py`
- Modify: `packages/router-core/tests/integration/test_local_control_plane.py`

**Interfaces:**
- Produces: `ProfileSourceClass` values `user-workspace`, `managed-workspace`, `user-personal`, `managed-personal`.
- Produces: `LayeredRoutingProfile(profile, source_class, source_digest, workspace_digest)`.
- Produces: `RoutingProfileRepository.load_ranked_layers(workspace_root, workspace_digest)`.
- Produces: `resolve_layered_profile_route(...)`; retain the current `resolve_profile_route(...)` wrapper for existing user-owned-only callers.

- [ ] **Step 1: Write failing fixed precedence tests**

Assert this exact order regardless of Rule Priority:

```text
user-owned Workspace
managed Workspace-local
user-owned Personal
managed Personal
built-in
```

An explicit Skill continues to bypass all Profile layers in `LocalControlPlaneService.plan_work`.

- [ ] **Step 2: Implement fixed managed paths**

```text
profiles/managed/personal/adaptive-memory.json
profiles/managed/workspace/<workspace-digest-without-prefix>/adaptive-memory.json
```

Workspace Digest derives from the already verified Workspace Root but only the digest becomes part of the path and metadata. Reject invalid digest format and symlink/reparse boundaries.

- [ ] **Step 3: Add Layer wrapper and resolver rank**

Rank by `ProfileSourceClass` before Rule Priority/Specificity. Do not mutate Rule Priority to simulate ownership. Public result route sources become `managed-workspace-profile` and `managed-personal-profile` in addition to current values.

- [ ] **Step 4: Preserve graceful routing on corrupt Managed Profile**

A corrupt Managed Profile disables only that managed layer, adds a sanitized `managed-profile-invalid` warning, and continues with User-owned Profile or built-in routing. Corrupt User-owned Profile retains the existing fail-closed behavior.

- [ ] **Step 5: Enable reviewed `managed-workspace-local` materialization**

Update the M2-C target matrix so an approved reviewed proposal can write the fixed digest-scoped managed file without modifying `.codex/workflow-skill-router.json`.

- [ ] **Step 6: Update Python and TypeScript result enums**

Even though Memory MCP tools are not public yet, `plan_work.route_source` output must accept the two managed source values before managed files are loaded at runtime.

- [ ] **Step 7: Run M3-A tests**

```powershell
python -m unittest packages.router-core.tests.profiles.test_profile_layers -v
python -m unittest packages.router-core.tests.memory.test_managed_profiles -v
python -m unittest packages.router-core.tests.profiles.test_resolver -v
python -m unittest packages.router-core.tests.integration.test_local_control_plane -v
cd plugins/workflow-skill-router
npm run check
```

- [ ] **Step 8: Commit M3-A**

```powershell
git add packages/router-core/src/workflow_skill_router/profiles packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/local_control.py packages/router-core/src/workflow_skill_router/service_models.py packages/router-core/tests plugins/workflow-skill-router/mcp/src/tool-output-schemas.ts
git commit -m "feat(memory): route through managed profile layers"
```

---

### Task 10: M3-B — Automatic Managed Promotion、Conflict Suppression 與 Notifications

**Files:**
- Create: `packages/router-core/tests/memory/test_automatic_promotion.py`
- Create: `packages/router-core/tests/memory/test_memory_notifications.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/candidates.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/backtest.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/proposals.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/materializer.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`

**Interfaces:**
- Produces: `AutomaticPromotionDecision(status, candidate_id, target, gate_reasons, revision_id, notification)`.
- Produces: `MemoryService.promote_eligible_candidates(now) -> tuple[AutomaticPromotionDecision, ...]`.
- Produces local notification types `candidate-created`, `auto-promotion-applied`, `auto-promotion-suppressed`, and `retention-purge`.

- [ ] **Step 1: Write automatic hard-invariant tests**

Automatic promotion must reject User-owned target, R3, user-explicit route without explicit remember-once, unknown Skill, low/medium confidence, hard contract violation, weaker thresholds, manual Profile conflict, and missing Backtest.

- [ ] **Step 2: Write successful managed promotion test**

Create five consistent successful observations on three dates. Assert one high-confidence Candidate, one managed Profile Revision, one fixed managed file, Candidate status `auto-promoted`, and visible notification.

- [ ] **Step 3: Implement Automatic Promotion Gate**

Run after Candidate generation only when Effective Mode is `automatic`. Bind the Candidate and Policy Digests, rerun Backtest immediately before write, and use the same CAS/Revision/Atomic materializer as reviewed writes.

- [ ] **Step 4: Implement conflict suppression**

If a Candidate overlaps or conflicts with a User-owned Profile, store a suppression bound to Material Evidence Digest and reason `candidate-conflict`; do not rewrite the manual Profile and do not silently choose a different Skill Tree.

- [ ] **Step 5: Implement mandatory automatic notifications**

`show_auto_promotion` is always true in V1. Notifications contain IDs, digests, target class, revision ID, and reason codes only. They do not contain Objective, local paths, or Profile instruction content.

- [ ] **Step 6: Add CLI automatic run/status**

```text
workflow-skill-router memory candidates promote-eligible
workflow-skill-router memory notifications list
```

The CLI operation is deterministic and local; it does not establish a background scheduler.

- [ ] **Step 7: Run M3-B tests**

```powershell
python -m unittest packages.router-core.tests.memory.test_automatic_promotion -v
python -m unittest packages.router-core.tests.memory.test_memory_notifications -v
python -m unittest discover -s packages/router-core/tests/memory -v
```

- [ ] **Step 8: Commit M3-B**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/memory
git commit -m "feat(memory): promote safe managed workflows automatically"
```

---

### Task 11: M4-A — Typed MCP Memory Surface 與 Runtime Readiness

**Files:**
- Modify: `packages/router-core/src/workflow_skill_router/service_models.py`
- Modify: `packages/router-core/src/workflow_skill_router/service_codecs.py`
- Modify: `packages/router-core/src/workflow_skill_router/tool_dispatch.py`
- Modify: `packages/router-core/src/workflow_skill_router/runtime_readiness.py`
- Modify: `packages/router-core/src/workflow_skill_router/local_control.py`
- Modify: `packages/router-core/tests/bridge/test_service_codecs.py`
- Modify: `packages/router-core/tests/plugin/test_tool_dispatch.py`
- Modify: `packages/router-core/tests/integration/test_local_control_plane.py`
- Modify: `plugins/workflow-skill-router/mcp/src/tool-definitions.ts`
- Modify: `plugins/workflow-skill-router/mcp/src/tool-schemas.ts`
- Modify: `plugins/workflow-skill-router/mcp/src/tool-output-schemas.ts`
- Modify: `plugins/workflow-skill-router/mcp/src/server.ts`
- Modify: `plugins/workflow-skill-router/mcp/src/workspace-roots.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/tool-surface.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/tool-metadata.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/tool-output.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/runtime-output-validation.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/runtime-readiness.test.ts`
- Modify: `plugins/workflow-skill-router/mcp/test/bundled-runtime.test.ts`
- Modify: `scripts/build-mcp-reference-data.mjs`
- Modify: `site/src/data/mcp-tools.generated.json`

**Interfaces:**
- Adds public tools: `get_memory_status`, `remember_workflow`, `record_route_feedback`, `list_workflow_candidates`, `preview_profile_update`, `transition_profile_update`, `rollback_profile_revision`, `purge_workflow_memory`.
- Public tool count becomes 20; runtime readiness and MCP `tools/list` must contain the identical set.
- `LocalControlPlaneService` delegates every Memory method to one `MemoryService`; no duplicate business logic.

- [ ] **Step 1: Write failing Python tool-set parity tests**

Add all eight names to expected codecs, dispatcher tools, and readiness. Strictly reject unknown fields and transition attempts that try to replace bound Candidate/Profile content.

- [ ] **Step 2: Add Python command/result dataclasses**

Use strict typed inputs. Workspace-aware tools accept `workspace_root: str | None` only so the MCP server can bind an approved root; no command accepts a target filesystem path. Mutations include expected state/digest, idempotency key, and correlation ID where applicable.

- [ ] **Step 3: Add readiness entries**

Recommended boundaries:

| Tool | Availability | Risk | Notes |
| --- | --- | --- | --- |
| `get_memory_status` | `local-ready` | R0 | no DB creation when disabled |
| `remember_workflow` | `local-ready` | R0 | policy/eligibility controls writes |
| `record_route_feedback` | `local-ready` | R0 | typed metadata only |
| `list_workflow_candidates` | `local-ready` | R0 | read only |
| `preview_profile_update` | `local-ready` | R0 | read/backtest only |
| `transition_profile_update` | `conditional-local` | R1 | managed/local target or verified Host Workspace authority |
| `rollback_profile_revision` | `conditional-local` | R1 | same target authority as materialization |
| `purge_workflow_memory` | `local-ready` | R1 | explicit digest-bound destructive confirmation |

Do not describe all 20 tools as local-ready; publish the exact matrix.

- [ ] **Step 4: Generalize trusted Workspace Root binding**

`server.ts` currently binds only `plan_work`. Extend `workspace-roots.ts` with one binder that supports the exact Memory tools containing `workspace_root`, preserves all other arguments, and rejects unadvertised roots before calling Python.

- [ ] **Step 5: Add strict Zod input/output schemas**

Enumerate Mode, Target, Feedback Type, Purge Scope, Candidate Status, Confidence, Authority Mode, Digest, and Reason Codes. `transition_profile_update` input must not contain Candidate, Target, Diff, Matcher, or Profile Document.

- [ ] **Step 6: Add MCP metadata and annotations**

Read-only tools: status, candidate list, preview. `purge_workflow_memory` sets `destructiveHint: true`; automatic/open-world hints remain false. Descriptions explicitly state Default-off, managed-only automatic writes, and no Skill/Runtime authority.

- [ ] **Step 7: Update reference generator cleanup**

The temporary State Directory cleanup must remove Router DB, Memory DB, WAL/SHM files, managed test profiles, and empty directories without assuming Memory DB exists. Generated reference must reject local paths and secret names as before.

- [ ] **Step 8: Regenerate bundles and reference data**

```powershell
python plugins/workflow-skill-router/scripts/build-runtime.py
Set-Location plugins/workflow-skill-router
npm ci
npm run check
Set-Location ../..
node scripts/build-mcp-reference-data.mjs
node scripts/build-mcp-reference-data.mjs --check
```

- [ ] **Step 9: Run full MCP tests**

```powershell
Set-Location plugins/workflow-skill-router
npm run check
node ./scripts/smoke-plugin.mjs
Set-Location ../..
python -m unittest discover -s packages/router-core/tests/bridge -v
python -m unittest discover -s packages/router-core/tests/plugin -v
```

- [ ] **Step 10: Commit M4-A**

```powershell
git add packages/router-core/src packages/router-core/tests plugins/workflow-skill-router/mcp plugins/workflow-skill-router/runtime/workflow_skill_router.pyz scripts/build-mcp-reference-data.mjs site/src/data/mcp-tools.generated.json
git commit -m "feat(plugin): expose adaptive workflow memory tools"
```

---

### Task 12: M4-B — Public Documentation、Examples、Flight Recorder 與 Pilot Gate

**Files:**
- Create: `site/src/content/docs/concepts/adaptive-workflow-memory.md`
- Create: `site/src/content/docs/zh-tw/concepts/adaptive-workflow-memory.md`
- Create: `site/src/content/docs/guides/configure-workflow-memory.md`
- Create: `site/src/content/docs/zh-tw/guides/configure-workflow-memory.md`
- Create: `site/src/content/docs/guides/migrate-to-workflow-memory.md`
- Create: `site/src/content/docs/zh-tw/guides/migrate-to-workflow-memory.md`
- Create: `starter/v2/workflow-skill-router/assets/workflow-memory.disabled.yaml`
- Create: `starter/v2/workflow-skill-router/assets/workflow-memory.reviewed.yaml`
- Create: `starter/v2/workflow-skill-router/assets/workflow-memory.automatic.json`
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `site/astro.config.mjs`
- Modify: `site/src/content/docs/reference/cli.md`
- Modify: `site/src/content/docs/zh-tw/reference/cli.md`
- Modify: `site/src/content/docs/reference/local-state.md`
- Modify: `site/src/content/docs/zh-tw/reference/local-state.md`
- Modify: `site/src/content/docs/reference/security-boundaries.md`
- Modify: `site/src/content/docs/zh-tw/reference/security-boundaries.md`
- Modify: `site/src/content/docs/reference/mcp-tools.mdx`
- Modify: `site/src/content/docs/zh-tw/reference/mcp-tools.mdx`
- Modify: `demo/v2-scenarios/schema.json`
- Modify: `demo/v2-scenarios/inputs.json`
- Modify: `scripts/build-v2-demo-data.py`
- Modify: `site/src/components/HomeLanding.astro`
- Modify: `site/src/content/docs/showcase.md`
- Modify: `site/src/content/docs/zh-tw/showcase.md`
- Modify: `tests/test_doc_parity.py`
- Modify: `tests/test_v2_documentation.py`
- Modify: `tests/test_skill_source_sync.py`

**Interfaces:**
- Public docs must teach `disabled`, `observe`, `reviewed`, and `automatic` with copy-pasteable JSON/YAML.
- Flight Recorder adds only fixture/sanitized traces for Policy Resolution, Observe, Reviewed Proposal, Automatic Managed Promotion, and Purge.
- No documentation may claim background learning, telemetry, automatic installation, user-file automatic writes, or verified activation.

- [ ] **Step 1: Write failing documentation contract tests**

Require bilingual routes and exact safety phrases:

```text
default-off
disabled < observe < reviewed < automatic
Workspace Policy cannot elevate Personal Policy
automatic-managed
intended-unverified
no telemetry
purge does not delete user-owned profiles
```

Update navigation parity to include the new Concept and Configuration Guide.

- [ ] **Step 2: Publish the configuration guide**

Document fixed paths for Windows/macOS/Linux, `WORKFLOW_SKILL_ROUTER_DATA_DIR`, Personal Ceiling, Workspace Restriction, file ambiguity, YAML subset, every feature override, Retention/Purge, and all three tracked examples.

- [ ] **Step 3: Package synchronized examples**

Copy canonical examples into Starter and generated Plugin Skill assets through the established source-sync mechanism. Add parity tests comparing source examples byte-for-byte after canonical generation; do not hand-edit generated archives.

- [ ] **Step 4: Update Local State and Security docs**

Explicitly separate Operational Router DB from Optional Memory DB; state that disabling does not delete; document purge scopes, managed profile paths, Revision snapshots, and the four separate Install/Activate/Runtime/Side-effect decisions.

- [ ] **Step 5: Add Flight Recorder fixture scenarios**

Extend `demo/v2-scenarios/schema.json` and `inputs.json` with sanitized scenarios. `scripts/build-v2-demo-data.py` must generate deterministic traces whose evidence class is `fixture-trace` or `runtime-trace`; public output cannot include actual Personal Memory content.

- [ ] **Step 6: Update homepage and showcase without overclaiming**

Describe Memory as opt-in Workflow Governance. Display Effective Mode, Candidate Evidence Summary, Diff/Revision, and Automatic Gate. Do not state that the Router learns semantic intent or works in the background.

- [ ] **Step 7: Add migration guide**

Existing users remain disabled. Explain how to start with `observe`, inspect History, move to `reviewed`, and only then enable `automatic`. Include backup/rollback/purge steps and explain that Skill-only cannot claim durable memory.

- [ ] **Step 8: Run documentation and site gates**

```powershell
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
python scripts/build-v2-demo-data.py --check
python -m unittest tests.test_doc_parity tests.test_v2_documentation tests.test_skill_source_sync -v
Set-Location site
npm ci
npm run assets:demo:check
npm run assets:social:check
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
```

- [ ] **Step 9: Run deterministic Pilot fixtures**

Create at least 20 sanitized local task records: 6 Single、8 Phased、6 Goal-like; at least 8 use a Routing Profile. Verify Default-off, observe-only metrics, reviewed approval, automatic managed-only write, correction rate, suppression, rollback, and purge. Label results as local deterministic Pilot, not Real Model Evidence.

- [ ] **Step 10: Commit M4-B**

```powershell
git add README.md README.zh-TW.md site demo scripts starter tests
 git commit -m "docs: publish adaptive workflow memory guidance"
```

---

## 3. Repository-wide Verification Gate

Run this gate on every Slice after focused tests; skip Site commands only before a Slice touches Site files, but always run them on M4-A/M4-B.

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/validate-router.py starter/v2/workflow-skill-router
python scripts/validate-router.py --public-readiness .
python scripts/audit-public-readiness.py .
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
python plugins/workflow-skill-router/scripts/build-runtime.py --check
node scripts/build-mcp-reference-data.mjs --check
Set-Location plugins/workflow-skill-router
npm ci
npm run check
node ./scripts/smoke-plugin.mjs
Set-Location ../..
git diff --check
```

For M4-A/M4-B additionally run:

```powershell
Set-Location site
npm ci
npm run assets:demo:check
npm run assets:social:check
npm run build
npm run test:site:smoke
npm run test:site:visual
npm run audit:lighthouse
Set-Location ..
```

No live model evaluation runs as part of this feature gate. M5 begins only if a separate Pilot report demonstrates the ADR 0004 semantic recommender decision conditions.

---

## 4. Spec Coverage Matrix

| Spec requirement | Implementation tasks |
| --- | --- |
| Default-off, no DB | Tasks 1–3 |
| JSON/YAML fixed policy, canonical digest | Tasks 1–2 |
| Personal ceiling / Workspace restriction | Task 2 |
| Separate purgeable store | Tasks 3 and 5 |
| Remember This Workflow | Task 4 |
| No Raw Prompt/path/content/secrets | Tasks 1, 4, 5, 12 |
| Route Feedback | Task 5 |
| History Analytics | Task 5 |
| Deterministic Candidate | Task 6 |
| Rejection suppression | Tasks 6 and 10 |
| Diff and Backtest | Task 7 |
| Reviewed approval | Tasks 7–8 |
| CAS, atomic write, revision, rollback | Task 8 |
| Managed Profile precedence | Task 9 |
| Automatic managed-only write | Task 10 |
| Typed MCP tools | Task 11 |
| Flight Recorder and bilingual docs | Task 12 |
| Skill/Runtime/Side-effect authority separation | Global Constraints and Tasks 9–12 |
| Semantic recommender remains gated | Global Constraints and Repository Gate |

---

## 5. Completion Definition

Adaptive Workflow Memory is implementation-complete only when all conditions hold:

1. No-policy installations remain byte-for-byte behaviorally equivalent for normal routing and create no Memory DB.
2. Equivalent JSON/YAML Policies resolve to one Canonical Digest on Windows, macOS, and Linux.
3. Workspace content cannot elevate memory or write autonomy.
4. Optional History is sanitized, bounded, export-redacted, and purgeable.
5. Reviewed Mode cannot write before bound approval, Diff, Backtest, CAS, and Revision.
6. Automatic Mode can write only fixed Router-managed targets after the stronger gate.
7. User-owned Profiles outrank Managed Profiles without priority manipulation.
8. Rollback creates a new Forward Revision.
9. All 20 MCP tools, Python readiness, TypeScript schemas, generated reference, and docs are synchronized.
10. Exact-head Required Checks and post-merge `main` CI pass for every Slice.
11. Public docs disclose limits and never imply semantic learning, telemetry, automatic permission, or verified Skill activation.
12. M5 remains a separate evidence-based decision, not an implicit continuation of this implementation.
