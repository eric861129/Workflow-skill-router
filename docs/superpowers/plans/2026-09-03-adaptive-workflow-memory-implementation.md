# Adaptive Workflow Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以預設關閉、Local-first、可清除、可審核、可版本化及可回滾的方式，為 Workflow Skill Router 加入 Workflow Memory、History Analytics、Reviewed Profile Promotion 與 Automatic Managed Memory。

**Architecture:** 新增獨立的 `workflow_skill_router.memory` bounded context，分離 Memory Policy、Optional History Store、Observation、Analytics、Candidate、Profile Proposal、Revision 與既有 Routing／Operational Event Store。先完成 deterministic、CLI-visible 的 Core，再一次性接入 typed MCP surface。任何記憶結果仍只代表 `intended-unverified` route，不取得 Skill activation、Runtime、Side Effect 或 Native Goal authority。

**Tech Stack:** Python 3.11+ standard library、SQLite、JSON Schema Draft 2020-12、TypeScript、Node.js 24+、Zod、Model Context Protocol、Astro/Starlight、`unittest`、Node test runner、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-09-03-adaptive-workflow-memory-design.md`

## Global Constraints

- 沒有有效 Personal Memory Policy 時，Effective Mode 必須是 `disabled`，不得建立 Memory DB、Observation、Candidate、Managed Profile 或 Remember Prompt。
- Autonomy order 固定為 `disabled < observe < reviewed < automatic`；Workspace Policy 只能降低 Personal Ceiling，不能自行開啟或提高記憶能力。
- Personal Policy 固定放在 `<router-data-dir>/config/workflow-memory.{json,yaml,yml}`；Workspace Policy 固定放在 `<trusted-workspace-root>/.codex/workflow-memory.{json,yaml,yml}`。
- 同一 Scope 同時存在兩種以上格式時，該 Scope 回傳 `ambiguous-memory-policy` 並停用；不得依檔名順序選一份。
- Python Core 維持零 Runtime dependency。YAML 使用 restricted YAML 1.2 parser，不加入 PyYAML 或可執行型別 Loader。
- Policy 檔案必須是 UTF-8、Regular Non-link File、最大 64 KiB。YAML 禁止 Anchor、Alias、Merge Key、Tag、多文件、Duplicate Key、Tab indentation、Block Scalar 與 Flow Collection。
- Canonical JSON 是唯一 Digest 表示；語意等價的 JSON 與 YAML 必須得到相同 `sha256:` Digest。
- 預設永久禁止保存 Raw Prompt、完整 Objective、Absolute Path、File Content、Tool Arguments、Secrets 與 Skill Instruction Body；Objective 與 Workspace Identity 只允許 Digest 或 `never`。
- Optional Memory History 使用獨立 SQLite Store，支援 Retention 與 Purge；不得把可選學習歷史只寫入既有 append-only `workflow_events`。
- 已發布的 Operational Migration 不得修改。Memory Store 使用自己的 append-only migration package、checksum 與 schema version。
- `workflow-skill-router/routing-profile@1.0.0` 不加入 History、Confidence、Retention 或 Memory 欄位。
- User-owned Personal／Workspace Profile 不得被 Automatic Mode 寫入。Automatic Mode 只能寫 Router-managed Personal 或 Router-managed Workspace-local Profile。
- 每次 Router-mediated Profile Write 必須完成 Strict Decode、Profile Lint、Conflict Check、Backtest、Expected Digest、Compare-and-Swap、Atomic Replace、Post-write Validation 與 Profile Revision。
- Rollback 以目前版本為基準建立新的 Forward Revision；不得刪除或改寫既有 Revision。
- User explicit Skill Lock 永遠優先；Rejected Support Skill 不得因 Memory Candidate 被重新加入當次 route。
- Remembered Skill Tree 仍是 `intended-unverified`；Memory 不安裝 Skill／Plugin、不啟用 Instructions、不授權 Filesystem／Network／Subprocess／Secrets、不授權 Deployment／Publication／Production，也不修改 Native Codex Goal。
- 第一版只使用 deterministic route signatures、thresholds、pattern mining 與 backtest；不加入 Embedding 或 LLM direct persistence。
- Default CI 不呼叫 Live Model、不消耗 Provider Quota，也不把 Fixture 宣稱為 Model Evidence。
- 每個垂直切片從前一切片合併後的最新 `main` 建立獨立 Branch 與 Draft PR；使用者核准前不得轉 Ready 或 Merge。
- 每個 Draft PR 必須在 exact pushed head 上完成 Focused Tests、Core Gate、Plugin Gate 及適用的 Site Gate；head 改變後重新跑 Gate。
- 合併採 Squash Merge；合併後必須確認 `main` 的 push-triggered CI，而不是只依賴 PR Check。

---

## 1. Delivery Topology

本功能分成 12 個實作切片。每個切片完成一個可執行、可測試的垂直成果，不在同一 PR 混合不同 Authority Boundary。

| Slice | Branch | Deliverable | Depends on |
| --- | --- | --- | --- |
| S0 | `codex/adaptive-workflow-memory-spec` | 已核准規格、ADR、範例與本計畫 | none |
| M0-A | `codex/memory-m0-policy-contract` | Memory Policy Schema、restricted YAML、Canonical Digest | S0 merged |
| M0-B | `codex/memory-m0-policy-resolution` | Fixed-location Loader、Personal/Workspace Resolver、CLI | M0-A |
| M1-A | `codex/memory-m1-store` | Default-off Optional Memory Store 與獨立 Migrations | M0-B |
| M1-B | `codex/memory-m1-observations` | Completed Workflow Reader、Eligibility、Observation、Remember command | M1-A |
| M1-C | `codex/memory-m1-analytics` | Typed Feedback、History Summary、Retention、Export、Purge | M1-B |
| M2-A | `codex/memory-m2-candidates` | Pattern Mining、Candidate Gate、Suppression | M1-C |
| M2-B | `codex/memory-m2-profile-proposals` | Profile Diff、Backtest、Proposal State Machine | M2-A |
| M2-C | `codex/memory-m2-revisions` | CAS、Atomic Materializer、Revision、Reviewed Write、Rollback | M2-B |
| M3-A | `codex/memory-m3-managed-profiles` | Managed Profile Storage 與固定 Layer Precedence | M2-C |
| M3-B | `codex/memory-m3-automatic-promotion` | Automatic Managed Promotion、Conflict Suppression、Notifications | M3-A |
| M4-A | `codex/memory-m4-mcp-surface` | 8 個 Typed MCP Memory Tools、Readiness、Generated Reference | M3-B |
| M4-B | `codex/memory-m4-docs-flight-recorder` | 中英文文件、範例封裝、Flight Recorder、Pilot Guide | M4-A |

### 每個 Slice 的固定流程

1. 使用 `superpowers:using-git-worktrees` 從最新 `main` 建立隔離 Worktree。
2. 建立上表指定 Branch，立刻 Push 並開 Draft PR。
3. 先寫失敗測試，再寫最小實作；一個行為群組一個 Commit。
4. 執行 Slice Focused Tests，再執行 Repository Gate。
5. 比對本機 SHA、Remote Branch SHA 與 PR Head SHA；三者必須一致。
6. Required Checks 必須對 exact head 完成；不得以較舊 SHA 的綠燈取代。
7. 回報 User-visible Contract、Diff、Proof 與 Remaining Limits，等待使用者核准。
8. 核准後轉 Ready、Squash Merge、刪除遠端 Branch。
9. 讀取 `main` 新 Merge SHA，確認 push-triggered CI。
10. 下一 Slice 只能從此 `main` SHA 建立。

---

## 2. Target Structure and Artifact Contracts

```text
packages/router-core/src/workflow_skill_router/
  memory/
    __init__.py
    models.py
    policy.py
    safe_yaml.py
    policy_io.py
    policy_resolver.py
    migrator.py
    store.py
    workflow_reader.py
    observations.py
    feedback.py
    analytics.py
    candidates.py
    backtest.py
    profile_diff.py
    proposals.py
    revisions.py
    materializer.py
    managed_profiles.py
    service.py
    migrations/
      __init__.py
      0001_observations.sql
      0002_candidates.sql
      0003_profile_changes.sql
  cli/
    memory.py
```

公開或持久化資料使用下列獨立 JSON Schemas；Routing Profile Schema 保持不變：

```text
memory-policy.schema.json
memory-policy-snapshot.schema.json
route-observation.schema.json
route-feedback.schema.json
workflow-pattern.schema.json
workflow-candidate.schema.json
profile-update-proposal.schema.json
profile-revision.schema.json
```

M0-A 將 `test_schema_documents.py` 從脆弱的「固定數量」檢查改為「Expected Filename Set + Unique `$id` + Draft 2020-12」檢查。後續切片加入 Schema 時，必須同步擴充 Expected Set 與該 Artifact 的 Contract Test。

既有檔案只負責接線：

- `local_control.py`：建立一次 `MemoryService` 並委派 typed operation，不放 Policy／Analytics／Promotion business logic。
- `profiles/storage.py`：共用 secure fixed-path I/O，並載入 Managed Profile layers。
- `profiles/resolver.py`：新增明確 Profile Layer rank，不用 Rule Priority 模擬 ownership。
- `service_models.py`、`service_codecs.py`、`tool_dispatch.py`、`runtime_readiness.py`：M4-A 才公開 MCP Memory contracts。
- TypeScript MCP files：M4-A 一次加入完整 public surface，避免 Core Slice 反覆改動工具數量。

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
- `MemoryMode`, `MemoryScope`, `MemoryPolicy`, `MemoryPolicyError`.
- `decode_memory_policy(document: Mapping[str, object], *, expected_scope: MemoryScope | None = None) -> MemoryPolicy`.
- `memory_policy_document(policy: MemoryPolicy) -> dict[str, object]`.
- `parse_safe_yaml(text: str) -> Mapping[str, object]`.
- `decode_policy_text(text: str, *, format: Literal["json", "yaml"], expected_scope: MemoryScope | None = None) -> MemoryPolicy`.

- [ ] **Step 1: Write failing schema inventory tests**

```python
EXPECTED_SCHEMA_FILES = {
    "artifact-envelope.schema.json",
    "capability-drift.schema.json",
    "capability-snapshot.schema.json",
    "capability.schema.json",
    "routing-profile.schema.json",
    "memory-policy.schema.json",
}


def test_schema_inventory_is_explicit(self) -> None:
    paths = sorted(SCHEMA_ROOT.glob("*.json"))
    self.assertEqual(EXPECTED_SCHEMA_FILES, {path.name for path in paths})
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    self.assertEqual(len(documents), len({item["$id"] for item in documents}))
```

Add a Policy-specific assertion for strict fields and the four modes.

- [ ] **Step 2: Run and verify RED**

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

Expected: FAIL because the new Schema does not exist.

- [ ] **Step 3: Add the strict Memory Policy Schema**

Minimal valid document:

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

Optional sections are `storage`, `privacy`, `eligibility`, `features`, and `notifications`. Every nested object uses `additionalProperties: false`.

- [ ] **Step 4: Write failing Python contract tests**

```python
def test_minimal_policy_uses_disabled_preset(self) -> None:
    policy = decode_memory_policy(minimal_policy("disabled"))
    self.assertEqual(MemoryMode.DISABLED, policy.mode)
    self.assertEqual("none", policy.capture)
    self.assertEqual("disabled", policy.features.remember_this_workflow.mode)
    self.assertRegex(policy.policy_digest, r"^sha256:[0-9a-f]{64}$")


def test_automatic_threshold_cannot_be_weaker(self) -> None:
    document = full_policy("automatic")
    document["eligibility"]["minimum_distinct_runs_automatic"] = 2
    with self.assertRaisesRegex(MemoryPolicyError, "automatic-threshold-weaker"):
        decode_memory_policy(document)
```

Cover exact fields, scope/policy ID agreement, preset expansion, target restrictions, forbidden privacy values, threshold ordering, duplicate values and deterministic digest.

- [ ] **Step 5: Implement immutable contract models and presets**

Use string enums and frozen dataclasses. Compute Digest from the normalized document only:

```python
policy_digest = "sha256:" + hashlib.sha256(
    canonical_json(normalized_document).encode("utf-8")
).hexdigest()
```

Source path, extension and YAML comments never enter the Digest.

- [ ] **Step 6: Write failing YAML safety tests**

Reject Anchor/Alias/Merge, Tag, multiple documents, Duplicate Key, Tab indentation, Block Scalar and Flow Collection. Accept block mappings/lists, two-space indentation, full-line comments and JSON-compatible scalar values.

- [ ] **Step 7: Implement the zero-dependency parser**

Algorithm:

1. Normalize CRLF; reject NUL and BOM.
2. Ignore blank lines and full-line comments only.
3. Require indentation in multiples of two and reject tabs.
4. Parse block mappings and `-` sequences with an indentation stack.
5. Reject duplicate keys before insertion.
6. Parse only `null`, booleans, base-10 integers, finite decimals, JSON double-quoted strings and restricted plain strings.
7. Reject YAML control syntax outside a JSON double-quoted scalar.
8. Return only JSON-compatible values.

- [ ] **Step 8: Lock JSON/YAML parity**

Load `docs/architecture/examples/workflow-memory.reviewed.yaml` and an equivalent JSON document; assert equal normalized documents and equal Digests. Comments and key order must not alter the result.

- [ ] **Step 9: Run GREEN and bundle checks**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_contract.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_safe_yaml.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
python plugins/workflow-skill-router/scripts/build-runtime.py
python plugins/workflow-skill-router/scripts/build-runtime.py --check
```

- [ ] **Step 10: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/schemas/json/v2/memory-policy.schema.json packages/router-core/tests/memory packages/router-core/tests/schemas/test_schema_documents.py
git commit -m "feat(memory): define strict memory policy contract"
git add plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "build(plugin): bundle memory policy contract"
```

---

### Task 2: M0-B — Fixed-location Loader、Effective Resolver 與 CLI

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

```python
@dataclass(frozen=True, slots=True)
class PolicyLoadResult:
    status: Literal["missing", "valid", "invalid", "ambiguous"]
    source: PolicySource | None
    reason_codes: tuple[str, ...]


class MemoryPolicyRepository:
    def inspect_personal(self) -> PolicyLoadResult: ...
    def inspect_workspace(self, workspace_root: Path) -> PolicyLoadResult: ...
    def validate_explicit_file(self, path: Path, expected_scope: MemoryScope) -> MemoryPolicy: ...
```

`inspect_*` never throws for malformed user configuration; it returns a sanitized invalid/ambiguous result so ordinary routing can continue with Memory disabled. `validate_explicit_file` is a CLI-only command and returns a non-zero error for invalid input.

- [ ] **Step 1: Write fixed-location tests**

Assert missing policy does not create the Data Root; exactly one JSON/YAML source loads; multiple formats return `ambiguous`; symlink, oversize and invalid UTF-8 return `invalid`; public result contains no absolute path.

- [ ] **Step 2: Implement fixed source inspection**

Only inspect the three fixed names. Resolve inside the approved root, reject links/reparse points, validate size before read and return sanitized reason codes.

- [ ] **Step 3: Write resolver tests**

```python
def test_workspace_cannot_elevate_personal_ceiling(self) -> None:
    result = resolve_effective_policy(
        personal=valid_result("personal", "observe"),
        workspace=valid_result("workspace", "automatic"),
    )
    self.assertEqual(MemoryMode.OBSERVE, result.mode)
    self.assertIn("workspace-policy-exceeds-ceiling", result.reason_codes)


def test_invalid_workspace_policy_disables_memory_for_workspace(self) -> None:
    result = resolve_effective_policy(
        personal=valid_result("personal", "automatic"),
        workspace=invalid_result("invalid-memory-policy"),
    )
    self.assertEqual(MemoryMode.DISABLED, result.mode)
```

- [ ] **Step 4: Implement deterministic intersection**

Resolution order:

```text
host hard disable
-> explicit no-memory
-> Personal ceiling
-> Workspace restriction
-> lower feature autonomy
-> stricter numeric limits
-> target set intersection
-> stricter privacy representation
```

Minimum evidence uses larger values; maximum rates/retention/counts use smaller values.

- [ ] **Step 5: Write and implement CLI tests**

Commands:

```text
workflow-skill-router memory status [--workspace <user-supplied-root>]
workflow-skill-router memory policy validate <file> --scope personal|workspace
workflow-skill-router memory policy explain [--workspace <user-supplied-root>]
```

`status` returns `disabled` and `personal-policy-missing` without creating a Memory DB. Stdout is canonical JSON and excludes full paths.

- [ ] **Step 6: Run tests**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_io.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_resolver.py" -v
python -m unittest discover -s packages/router-core/tests/cli -p "test_memory_cli.py" -v
python plugins/workflow-skill-router/scripts/build-runtime.py
python plugins/workflow-skill-router/scripts/build-runtime.py --check
```

- [ ] **Step 7: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli packages/router-core/tests/memory packages/router-core/tests/cli/test_memory_cli.py
git commit -m "feat(memory): resolve default-off memory policies"
git add plugins/workflow-skill-router/runtime/workflow_skill_router.pyz
git commit -m "build(plugin): bundle memory policy resolution"
```

---

### Task 3: M1-A — Optional Memory Store、Policy Snapshot 與 Migrations

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrator.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0001_observations.sql`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/memory-policy-snapshot.schema.json`
- Create: `packages/router-core/tests/memory/test_memory_migrator.py`
- Create: `packages/router-core/tests/memory/test_memory_store.py`
- Create: `packages/router-core/tests/memory/test_policy_snapshot.py`
- Modify: `packages/router-core/pyproject.toml`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- `memory_database_path(data_dir: Path) -> Path`, fixed to `memory/workflow-memory.sqlite3`.
- `MemoryStore.open_if_enabled(data_dir: Path, policy: EffectiveMemoryPolicy) -> MemoryStore | None`.
- `migrate_memory_store(database: Path) -> None` with independent checksums.
- `MemoryPolicySnapshot` records effective modes, source class, Digest, feature decisions and reason codes without full source content/path.

- [ ] **Step 1: Write Default-off and migration RED tests**

Disabled Policy returns `None` before touching the filesystem. Enabled Policy creates only the separate Memory DB. Repeated migration is idempotent; modified migration checksum fails; operational `router-v2.sqlite3` is unchanged.

- [ ] **Step 2: Add Policy Snapshot Schema and update expected Schema set**

The Schema is strict, redacted and contains no path or raw Policy document. Add its filename to `EXPECTED_SCHEMA_FILES`.

- [ ] **Step 3: Add memory migration package data**

Update `pyproject.toml`:

```toml
[tool.setuptools.package-data]
workflow_skill_router = [
  "schemas/json/**/*.json",
  "persistence/migrations/*.sql",
  "memory/migrations/*.sql",
]
```

Add a packaging test that builds/inspects the package or importlib resources and confirms `0001_observations.sql` is present.

- [ ] **Step 4: Create `0001_observations.sql`**

Tables:

```sql
memory_schema_migrations
memory_command_receipts
memory_policy_snapshots
route_observations
route_feedback
```

Use strict checks for mode, eligibility status, feedback type and source class. `route_observations` stores only canonical JSON payload and Digests; no plaintext objective/path column exists.

- [ ] **Step 5: Implement Memory-only migrator and lazy store**

The migrator scans only `workflow_skill_router.memory.migrations`. `open_if_enabled` does not create directories when capture is disabled; enabled modes reject symlink/reparse boundaries, migrate, enable foreign keys/WAL and expose bounded repository methods rather than raw writable connections.

- [ ] **Step 6: Run tests**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_memory_migrator.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_memory_store.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_policy_snapshot.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
python -m unittest discover -s packages/router-core/tests/persistence -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/schemas/json/v2/memory-policy-snapshot.schema.json packages/router-core/pyproject.toml packages/router-core/tests
git commit -m "feat(memory): add optional purgeable memory store"
```

---

### Task 4: M1-B — Completed Workflow Reader、Eligibility、Observation 與 Remember

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/workflow_reader.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/observations.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/route-observation.schema.json`
- Create: `packages/router-core/tests/memory/test_workflow_reader.py`
- Create: `packages/router-core/tests/memory/test_observations.py`
- Create: `packages/router-core/tests/memory/test_remember_workflow.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class MatcherSeed:
    objective_keywords: tuple[str, ...]
    domains: tuple[str, ...]
    tags: tuple[str, ...]
    source: Literal["trusted-routing-context", "existing-profile", "user-explicit"]


@dataclass(frozen=True, slots=True)
class RememberWorkflowCommand:
    context: MemoryRequestContext
    workflow_run_id: str
    workspace_root: Path | None
    matcher_seed: MatcherSeed | None
    target_profile_class: str
    risk_class: str
    side_effect_outcome: Literal["none", "known-success", "known-failure", "unknown"]
    one_shot: Literal["none", "remember-once", "no-memory"]
    idempotency_key: str
    correlation_id: str
```

- [ ] **Step 1: Add Route Observation Schema and reader tests**

Use `LocalControlPlaneService` fixtures. Bind read to session, actor and Runtime Policy Snapshot; reject incomplete, cross-session, corrupt or Native Goal-owned records.

- [ ] **Step 2: Implement read-only Completed Workflow projection**

Read `local_control_plans`, ordered `local_work_items` and ordered `local_work_transitions.observation_json`. A completed local snapshot requires every required item `completed` and every phase a persisted `local-gate` with `passed=true`. Do not return `reported_outcome` free text to Memory.

- [ ] **Step 3: Write route signature/privacy tests**

Signature contains Envelope, ordered Phases, Primary/Support Skill IDs, Exit Gate IDs, Profile source class, Matcher Seed, required capability classes and local evidence class. It excludes Objective, path, file content, Tool Arguments and Secrets.

- [ ] **Step 4: Implement eligibility**

Require terminal success, required gate pass, known side-effect outcome `none`/`known-success`, no `no-memory`, canonical Skill IDs, non-R3 risk, no pending consent and at least one Matcher Seed signal. User-explicit routes require Reviewed Mode or explicit `remember-once`; they are not automatically promotable.

Matcher material may come only from trusted domains/tags, the already matched Profile matcher, or explicit structured `MatcherSeed`. Never derive keywords from Raw Objective. No signal returns `insufficient-match-signal` without persisting an Observation.

- [ ] **Step 5: Implement `MemoryService.remember_workflow`**

```text
resolve current effective policy
-> stop before Store open when disabled/no-memory
-> read completed workflow
-> normalize Matcher Seed
-> evaluate eligibility
-> open Store only when capture is allowed
-> save redacted Policy Snapshot
-> replay receipt or insert one Observation
-> return public-safe result
```

`workflow_run_id` is unique in Observation storage, so Resume does not increment history.

- [ ] **Step 6: Add CLI `memory remember`**

Accept repeated `--keyword`, `--domain`, `--tag`, a fixed target enum, Risk and Side-effect enum. Do not accept a Profile destination path.

- [ ] **Step 7: Run tests**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_workflow_reader.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_observations.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_remember_workflow.py" -v
python -m unittest discover -s packages/router-core/tests/integration -p "test_local_work_loop.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

- [ ] **Step 8: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/src/workflow_skill_router/schemas/json/v2/route-observation.schema.json packages/router-core/tests
git commit -m "feat(memory): capture eligible workflow observations"
```

---

### Task 5: M1-C — Route Feedback、Analytics、Retention、Export 與 Purge

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/feedback.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/analytics.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/route-feedback.schema.json`
- Create: `packages/router-core/tests/memory/test_route_feedback.py`
- Create: `packages/router-core/tests/memory/test_history_analytics.py`
- Create: `packages/router-core/tests/memory/test_retention_and_purge.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- `RecordRouteFeedbackCommand` with typed feedback and standard reason code.
- `HistorySummaryQuery`, `HistorySummary` and stable Summary Digest.
- `PurgeMemoryCommand(scope, expected_summary_digest, include_managed_profiles, idempotency_key)`.

- [ ] **Step 1: Add Feedback Schema and contract tests**

Allowed types: `accepted`, `corrected`, `rejected`, `support-rejected`, `capability-unavailable`, `gate-failed`, `completed`, `abandoned`, `no-memory`. `corrected` requires original/corrected signature Digests and correction dimensions. Free text is rejected unless explicitly enabled and never enters Matcher generation.

- [ ] **Step 2: Implement typed transitions**

Bind Feedback to an existing Observation and Policy Digest. Enforce idempotency and reject cross-observation signature replacement.

- [ ] **Step 3: Implement deterministic analytics**

Calculate by distinct `workflow_run_id`: Route frequency, completion, gate pass, correction, consent rejection, capability unavailable, planned/actual consistency class, distinct active days, Workspace distribution and Profile source distribution. Confidence is `insufficient-evidence`, `low`, `medium` or `high`, never a model probability.

- [ ] **Step 4: Implement Retention and explicit Purge**

Purge scopes: `history-only`, `analytics-only`, `candidates-only`, `revisions-only`, `managed-profiles-only`, `all-memory-data`. M1 implements the first two and returns `scope-not-available` for future scopes. Purge requires exact pre-operation Summary Digest and one transaction. Disabling does not delete unless `purge_on_disable` is explicitly true.

- [ ] **Step 5: Implement redacted export**

Export canonical JSON with aggregate metrics and optional sanitized observations. Scan serialized output for objective/path/tool-argument keys and Router Data Root; reject on leak.

- [ ] **Step 6: Extend CLI and run tests**

```text
memory feedback record
memory history summary
memory history export
memory history purge --scope history-only --expected-summary-digest sha256:...
```

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_route_feedback.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_history_analytics.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_retention_and_purge.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/src/workflow_skill_router/schemas/json/v2/route-feedback.schema.json packages/router-core/tests
git commit -m "feat(memory): add route feedback and history analytics"
```

---

### Task 6: M2-A — Pattern Mining、Workflow Candidate 與 Suppression

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0002_candidates.sql`
- Create: `packages/router-core/src/workflow_skill_router/memory/candidates.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/workflow-pattern.schema.json`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/workflow-candidate.schema.json`
- Create: `packages/router-core/tests/memory/test_candidate_migration.py`
- Create: `packages/router-core/tests/memory/test_candidate_engine.py`
- Create: `packages/router-core/tests/memory/test_candidate_suppression.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- `PatternMetrics`, `WorkflowPattern`, `WorkflowCandidate`, `CandidateDecision`.
- `CandidateEngine.rebuild(scope: MemoryScope, now: datetime) -> tuple[WorkflowCandidate, ...]`.
- Candidate states: `proposed`, `rejected`, `expired`, `suppressed`, `superseded`, later `approved`/`auto-promoted`.

- [ ] **Step 1: Add Candidate migration and strict schemas**

Create `workflow_patterns`, `workflow_candidates`, `candidate_suppressions`. Schemas expose sanitized Matcher, Route, evidence summary, confidence category, target class and Digests.

- [ ] **Step 2: Implement deterministic grouping**

Group by Scope, normalized Matcher Seed, Envelope, ordered Phase/Skill/Gate route, Workspace Digest for workspace-local target and Profile Source Class. Different Matcher or Workspace never merges.

- [ ] **Step 3: Implement metrics and gates**

Reviewed default: 3 runs/2 days, success and gate `>=0.80`, correction `<=0.20`, route consistency `>=0.75`, zero hard violation.

Automatic default: 5 runs/3 days, success and gate `>=0.90`, correction `<=0.10`, consistency `>=0.85`, canonical Skill IDs, managed target, zero hard violation.

Return reason codes instead of a Candidate for insufficient evidence/signal, explicit route requiring review, unknown Skill, hard violation or non-managed automatic target.

- [ ] **Step 4: Implement rejection suppression**

Unchanged `material_evidence_digest` remains suppressed until configured expiry. New distinct successful evidence changes the Digest and permits a new Candidate.

- [ ] **Step 5: Add CLI and run tests**

```text
memory candidates rebuild
memory candidates list
memory candidates show <id>
memory candidates reject <id> --reason <code>
```

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_candidate_migration.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_candidate_engine.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_candidate_suppression.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/src/workflow_skill_router/schemas/json/v2 packages/router-core/tests
git commit -m "feat(memory): recommend deterministic workflow candidates"
```

---

### Task 7: M2-B — Profile Diff、Backtest 與 Bound Proposal

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/memory/migrations/0003_profile_changes.sql`
- Create: `packages/router-core/src/workflow_skill_router/memory/profile_diff.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/backtest.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/proposals.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/profile-update-proposal.schema.json`
- Create: `packages/router-core/tests/memory/test_profile_diff.py`
- Create: `packages/router-core/tests/memory/test_profile_backtest.py`
- Create: `packages/router-core/tests/memory/test_profile_proposals.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/models.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/store.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- `SemanticProfileDiff`, `JsonPatchOperation`, `BacktestSummary`, `ProfileUpdateProposal`.
- `build_profile_document(candidate, current_profile) -> Mapping[str, object]`.
- `diff_profiles(before, after) -> SemanticProfileDiff`.
- `backtest_profile_update(current_layers, proposed_profile, observations) -> BacktestSummary`.
- `transition_profile_update(proposal_id, action, expected_state_version, idempotency_key)`; action is `approve` or `reject` only.

- [ ] **Step 1: Add proposal table and Schema**

Migration creates `profile_update_proposals`; strict Schema binds Candidate, Target, expected Profile Digest, proposed Profile Digest, Diff Digest, Backtest Digest, Policy Digest and lifecycle.

- [ ] **Step 2: Implement stable Semantic + JSON Diff**

Cover Rule add/remove/change, Matcher, Priority, Work Mode, Phase order, Primary Skill, Support Skill and Exit Gate. Stable order is Rule ID, Phase position, field name.

- [ ] **Step 3: Implement deterministic Backtest**

Decode proposed content through the existing Routing Profile contract and run the same lexical/domain/tag/work-mode matching against stored structured Matcher Seeds. Report coverage, unexpected matches, shadowed/equal-rank conflict, manual precedence, capability gap class and Workspace isolation.

- [ ] **Step 4: Implement bound Proposal lifecycle**

```text
pending -> approved | rejected | stale | expired
```

Transition input cannot include Candidate, Target, Diff, Matcher or Profile document. Creating a Proposal requires zero Profile Lint errors and acceptable Backtest. Approval records intent only; no file write in this slice.

- [ ] **Step 5: Run tests**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_diff.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_backtest.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_proposals.py" -v
python -m unittest discover -s packages/router-core/tests/profiles -p "test_resolver.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

- [ ] **Step 6: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/schemas/json/v2/profile-update-proposal.schema.json packages/router-core/tests
git commit -m "feat(memory): create reviewable profile update proposals"
```

---

### Task 8: M2-C — Revision、CAS、Atomic Materializer 與 Rollback

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/profiles/atomic_io.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/revisions.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/materializer.py`
- Create: `packages/router-core/src/workflow_skill_router/schemas/json/v2/profile-revision.schema.json`
- Create: `packages/router-core/tests/profiles/test_atomic_io.py`
- Create: `packages/router-core/tests/memory/test_profile_revisions.py`
- Create: `packages/router-core/tests/memory/test_profile_materializer.py`
- Create: `packages/router-core/tests/memory/test_profile_rollback.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/storage.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/proposals.py`
- Modify: `packages/router-core/src/workflow_skill_router/memory/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/cli/memory.py`
- Modify: `packages/router-core/tests/schemas/test_schema_documents.py`

**Interfaces:**
- `secure_read_json(path, root, max_bytes)` and `atomic_write_canonical_json(path, root, document, expected_digest)`.
- `ProfileTarget(target_class, profile_id, workspace_digest, fixed_path_class)`; no arbitrary path.
- `ProfileRevisionStore.record/list/load_snapshot`.
- `ProfileMaterializer.apply_approved(proposal, authority) -> ProfileRevision`.
- `create_rollback_proposal(profile_id, selected_revision_id, current_digest)`.

- [ ] **Step 1: Extract and test secure I/O**

Preserve current Personal Profile behavior: root containment, regular non-link target, temp file in same directory, flush/fsync, atomic replace, cleanup and post-write Digest validation.

- [ ] **Step 2: Add Revision table/Schema and fixed snapshot layout**

`0003_profile_changes.sql` also creates `profile_revision_index`. Snapshot path:

```text
profiles/revisions/<target-class>/<profile-id>/<revision-id>.json
```

Schema records previous/new Digest, Proposal/Candidate, Policy, actor, authority, Diff, Backtest, status and Snapshot Digest.

- [ ] **Step 3: Implement target authority**

- `managed-personal`: Router-local managed authority.
- `managed-workspace-local`: unavailable until M3-A.
- `user-personal`: reviewed approval plus local user-owned write authority.
- `workspace-file`: reviewed approval plus verified Workspace Root and Host File Write Authority.

No caller-supplied target path.

- [ ] **Step 4: Implement CAS and write recovery**

Load approved Proposal, verify current Digest, record pending Revision, atomically write fixed target, strict re-read, finalize. Drift marks Proposal `stale` without overwrite. If file write succeeds but metadata finalization fails, reconcile by exact Snapshot Digest on replay rather than blindly rewriting.

- [ ] **Step 5: Implement Rollback as forward revision**

Selected old Snapshot produces a new Proposal/Diff against current state, passes approval/CAS, writes content and creates a new `rollback` Revision. Old Revision rows/files remain unchanged.

- [ ] **Step 6: Extend CLI and run tests**

Workspace writes remain unavailable from local CLI in this slice.

```powershell
python -m unittest discover -s packages/router-core/tests/profiles -p "test_atomic_io.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_revisions.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_materializer.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_profile_rollback.py" -v
python -m unittest discover -s packages/router-core/tests/schemas -p "test_schema_documents.py" -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/profiles packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/src/workflow_skill_router/schemas/json/v2/profile-revision.schema.json packages/router-core/tests
git commit -m "feat(memory): version and rollback reviewed profiles"
```

---

### Task 9: M3-A — Managed Profiles 與固定 Layer Precedence

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/profiles/layers.py`
- Create: `packages/router-core/src/workflow_skill_router/memory/managed_profiles.py`
- Create: `packages/router-core/tests/profiles/test_profile_layers.py`
- Create: `packages/router-core/tests/memory/test_managed_profiles.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/storage.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/resolver.py`
- Modify: `packages/router-core/src/workflow_skill_router/profiles/__init__.py`
- Modify: `packages/router-core/src/workflow_skill_router/local_control.py`
- Modify: `plugins/workflow-skill-router/mcp/src/tool-output-schemas.ts`
- Modify: `packages/router-core/tests/profiles/test_resolver.py`
- Modify: `packages/router-core/tests/integration/test_local_control_plane.py`

**Interfaces:**
- `ProfileSourceClass`: `user-workspace`, `managed-workspace`, `user-personal`, `managed-personal`.
- `LayeredRoutingProfile(profile, source_class, source_digest, workspace_digest)`.
- `RoutingProfileRepository.load_ranked_layers(workspace_root, workspace_digest)`.
- `resolve_layered_profile_route(...)`; preserve existing `resolve_profile_route(...)` wrapper.

- [ ] **Step 1: Write precedence tests**

Exact order regardless of Rule Priority:

```text
user-owned Workspace
managed Workspace-local
user-owned Personal
managed Personal
built-in
```

Explicit Skill bypasses all Profile layers.

- [ ] **Step 2: Implement fixed managed paths**

```text
profiles/managed/personal/adaptive-memory.json
profiles/managed/workspace/<workspace-digest-without-prefix>/adaptive-memory.json
```

Only verified Workspace Root produces the Digest. Reject invalid Digest and link/reparse boundaries.

- [ ] **Step 3: Add explicit Layer rank**

Rank source class before Rule Priority/Specificity. Do not alter Rule Priority. Add route sources `managed-workspace-profile` and `managed-personal-profile` to Python/TypeScript output contracts.

- [ ] **Step 4: Define corrupt managed behavior**

Corrupt Managed Profile disables only that managed layer, adds `managed-profile-invalid` warning and continues with User-owned/built-in route. Existing fail-closed behavior for corrupt User-owned Profile remains.

- [ ] **Step 5: Enable reviewed managed Workspace write and run tests**

```powershell
python -m unittest discover -s packages/router-core/tests/profiles -p "test_profile_layers.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_managed_profiles.py" -v
python -m unittest discover -s packages/router-core/tests/profiles -p "test_resolver.py" -v
python -m unittest discover -s packages/router-core/tests/integration -p "test_local_control_plane.py" -v
Set-Location plugins/workflow-skill-router
npm run check
Set-Location ../..
```

- [ ] **Step 6: Commit**

```powershell
git add packages/router-core/src/workflow_skill_router/profiles packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/local_control.py packages/router-core/tests plugins/workflow-skill-router/mcp/src/tool-output-schemas.ts
git commit -m "feat(memory): route through managed profile layers"
```

---

### Task 10: M3-B — Automatic Managed Promotion 與 Notifications

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
- `AutomaticPromotionDecision(status, candidate_id, target, gate_reasons, revision_id, notification)`.
- `MemoryService.promote_eligible_candidates(now) -> tuple[AutomaticPromotionDecision, ...]`.
- Notification types: `candidate-created`, `auto-promotion-applied`, `auto-promotion-suppressed`, `retention-purge`.

- [ ] **Step 1: Write hard-invariant tests**

Reject User-owned target, R3, user-explicit route without remember-once, unknown Skill, non-high confidence, hard violation, weaker thresholds, manual Profile conflict and missing Backtest.

- [ ] **Step 2: Write successful automatic test**

Five consistent successful runs on three dates produce one high Candidate, one Managed Revision, one fixed managed file, Candidate status `auto-promoted` and visible notification.

- [ ] **Step 3: Implement promotion gate**

Run only under Effective `automatic`. Bind Candidate/Policy Digests, rerun Backtest immediately before write and reuse the reviewed CAS/Revision/Atomic path.

- [ ] **Step 4: Implement conflict suppression and mandatory disclosure**

Overlap/conflict with User-owned Profile stores suppression and does not rewrite or silently choose a different route. `show_auto_promotion` remains true in V1. Notifications contain IDs/Digests/reasons only.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m unittest discover -s packages/router-core/tests/memory -p "test_automatic_promotion.py" -v
python -m unittest discover -s packages/router-core/tests/memory -p "test_memory_notifications.py" -v
python -m unittest discover -s packages/router-core/tests/memory -v
```

```powershell
git add packages/router-core/src/workflow_skill_router/memory packages/router-core/src/workflow_skill_router/cli/memory.py packages/router-core/tests/memory
git commit -m "feat(memory): promote safe managed workflows automatically"
```

---

### Task 11: M4-A — Typed MCP Memory Surface

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

**Public tools:**

```text
get_memory_status
remember_workflow
record_route_feedback
list_workflow_candidates
preview_profile_update
transition_profile_update
rollback_profile_revision
purge_workflow_memory
```

Existing 12 + new 8 = 20 tools. Python readiness, Python dispatcher/codecs, TypeScript definitions/schemas, MCP `tools/list` and generated reference must contain the identical set.

- [ ] **Step 1: Write failing Python parity/codec tests**

Strictly reject unknown fields and transition attempts that replace bound Candidate/Profile content. `LocalControlPlaneService` delegates to one `MemoryService` instance.

- [ ] **Step 2: Add readiness matrix**

| Tool | Availability | Risk |
| --- | --- | --- |
| `get_memory_status` | `local-ready` | R0 |
| `remember_workflow` | `local-ready` | R0 |
| `record_route_feedback` | `local-ready` | R0 |
| `list_workflow_candidates` | `local-ready` | R0 |
| `preview_profile_update` | `local-ready` | R0 |
| `transition_profile_update` | `conditional-local` | R1 |
| `rollback_profile_revision` | `conditional-local` | R1 |
| `purge_workflow_memory` | `local-ready` | R1 |

Do not describe all 20 as local-ready.

- [ ] **Step 3: Generalize trusted Workspace binding**

Extend the existing root binder to exact Memory tools containing `workspace_root`; reject unadvertised roots before Python. No binder accepts a target path.

- [ ] **Step 4: Add strict Zod input/output and metadata**

Enumerate Mode, Target, Feedback, Purge Scope, Candidate Status, Confidence, Authority, Digest and Reason. `transition_profile_update` cannot include Candidate, Target, Diff, Matcher or Profile document. Status/list/preview are read-only. Purge sets `destructiveHint: true`.

- [ ] **Step 5: Update reference cleanup and regenerate**

Temporary cleanup removes Router DB and optional Memory DB WAL/SHM plus managed test artifacts. Absence is valid.

```powershell
python plugins/workflow-skill-router/scripts/build-runtime.py
Set-Location plugins/workflow-skill-router
npm ci
npm run check
Set-Location ../..
node scripts/build-mcp-reference-data.mjs
node scripts/build-mcp-reference-data.mjs --check
```

- [ ] **Step 6: Run MCP/Core tests**

```powershell
Set-Location plugins/workflow-skill-router
npm run check
node ./scripts/smoke-plugin.mjs
Set-Location ../..
python -m unittest discover -s packages/router-core/tests/bridge -v
python -m unittest discover -s packages/router-core/tests/plugin -v
python -m unittest discover -s packages/router-core/tests/integration -p "test_local_control_plane.py" -v
```

- [ ] **Step 7: Commit**

```powershell
git add packages/router-core/src packages/router-core/tests plugins/workflow-skill-router/mcp plugins/workflow-skill-router/runtime/workflow_skill_router.pyz scripts/build-mcp-reference-data.mjs site/src/data/mcp-tools.generated.json
git commit -m "feat(plugin): expose adaptive workflow memory tools"
```

---

### Task 12: M4-B — Public Docs、Examples、Flight Recorder 與 Pilot

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
- Modify: bilingual `reference/cli.md`, `reference/local-state.md`, `reference/security-boundaries.md`, `reference/mcp-tools.mdx`
- Modify: `demo/v2-scenarios/schema.json`
- Modify: `demo/v2-scenarios/inputs.json`
- Modify: `scripts/build-v2-demo-data.py`
- Modify: `site/src/components/HomeLanding.astro`
- Modify: bilingual `showcase.md`
- Modify: `tests/test_doc_parity.py`
- Modify: `tests/test_v2_documentation.py`
- Modify: `tests/test_skill_source_sync.py`

- [ ] **Step 1: Write failing documentation contracts**

Require bilingual routes and exact concepts: Default-off, autonomy order, Workspace cannot elevate Personal, `automatic-managed`, `intended-unverified`, no telemetry and purge not deleting User-owned Profiles.

- [ ] **Step 2: Publish configuration and migration guides**

Document OS paths, data-root override, Personal/Workspace resolution, ambiguity, safe YAML, feature overrides, Retention/Purge and copy-paste examples. Existing users remain disabled; recommend `observe -> reviewed -> automatic` progression. Skill-only cannot claim durable memory.

- [ ] **Step 3: Package synchronized examples**

Copy canonical examples to Starter and generated Plugin Skill assets through the established sync process. Add source-sync tests; do not edit generated archives.

- [ ] **Step 4: Update Local State/Security/MCP references**

Separate Operational and Optional Memory DB, document managed/revision paths and four authority decisions. Publish exact 20-tool readiness matrix.

- [ ] **Step 5: Add sanitized Flight Recorder scenarios**

Scenarios: Policy Resolution, Observe, Reviewed Proposal, Automatic Managed Promotion and Purge. Evidence is `fixture-trace` or sanitized `runtime-trace`, never actual Personal Memory.

- [ ] **Step 6: Run docs/site/Pilot gates**

```powershell
python scripts/check-markdown-links.py .
python scripts/check-doc-parity.py
python scripts/build-v2-demo-data.py --check
python -m unittest discover -s tests -p "test_doc_parity.py" -v
python -m unittest discover -s tests -p "test_v2_documentation.py" -v
python -m unittest discover -s tests -p "test_skill_source_sync.py" -v
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

Pilot fixtures: at least 20 sanitized local records—6 Single, 8 Phased, 6 Goal-like; at least 8 use a Routing Profile. Verify Default-off, observe metrics, reviewed approval, automatic managed-only write, correction, suppression, rollback and purge. Label as deterministic local Pilot, not Model Evidence.

- [ ] **Step 7: Commit**

```powershell
git add README.md README.zh-TW.md site demo scripts starter tests
git commit -m "docs: publish adaptive workflow memory guidance"
```

---

## 3. Repository-wide Verification Gate

Run after every Slice; Site commands are mandatory for M4-A/M4-B and whenever Site files change.

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

M4 Site gate:

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

No live model evaluation runs as part of this feature. M5 starts only after a separate Pilot report satisfies ADR 0004's semantic recommender decision conditions.

---

## 4. Spec Coverage Matrix

| Requirement | Tasks |
| --- | --- |
| Default-off, no DB | 1–3 |
| Fixed JSON/YAML Policy and Digest | 1–2 |
| Personal Ceiling / Workspace Restriction | 2 |
| Separate purgeable Store | 3, 5 |
| Policy Snapshot Schema | 3 |
| Remember This Workflow | 4 |
| Route Observation Schema/privacy | 4 |
| Typed Feedback/Schema | 5 |
| History Analytics/Retention/Purge | 5 |
| Pattern/Candidate Schemas and engine | 6 |
| Rejection suppression | 6, 10 |
| Diff, Backtest, Proposal Schema | 7 |
| Reviewed approval | 7–8 |
| Revision Schema, CAS, atomic write, rollback | 8 |
| Managed Profile precedence | 9 |
| Automatic managed-only write | 10 |
| 8 typed MCP tools | 11 |
| Flight Recorder and bilingual docs | 12 |
| Authority separation | Global Constraints, 9–12 |
| Semantic recommender remains gated | Global Constraints, Repository Gate |

---

## 5. Completion Definition

Implementation is complete only when:

1. No-policy installations preserve normal routing behavior and create no Memory DB.
2. Equivalent JSON/YAML Policies produce one Canonical Digest on Windows/macOS/Linux.
3. Workspace content cannot elevate memory or write autonomy.
4. Optional History is sanitized, bounded, export-redacted and purgeable.
5. Reviewed Mode cannot write before bound approval, Diff, Backtest, CAS and Revision.
6. Automatic Mode writes only fixed Router-managed targets after the stronger gate.
7. User-owned Profiles outrank Managed Profiles without priority manipulation.
8. Rollback creates a new Forward Revision.
9. All 20 MCP tools, Python readiness, TypeScript schemas, generated reference and docs remain synchronized.
10. Exact-head Required Checks and post-merge `main` CI pass for every Slice.
11. Public docs never imply semantic learning, telemetry, automatic permission or verified Skill activation.
12. M5 remains a separate evidence-based decision, not an implicit continuation.
