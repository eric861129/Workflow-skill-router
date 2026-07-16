# Workflow Skill Router V2 Real Model Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立答案隔離、可重現且能誠實區分 Contract／Behavior／Outcome 的真實模型評測管線。

**Architecture:** 評測實作位於 Python core 的 `workflow_skill_router.evaluation`，authoring case 封裝時拆成 execution、driver、scoring 三個 package；Execution Runner 絕不可取得 ScoringKey。Server 依已驗證的 `RequestContext` 簽發不可由 client 建構或擴權的 Eval authorization；Host、External 與 Manual adapters 共用同一 sealed-result contract。Raw artifact 進入具 OS 權限保護或注入式 encryption-at-rest provider 的受限 store，scorer 再驗證 hash binding 與 deterministic hard invariants。Public review attestation 綁定不含 publication metadata 的 `review_subject_digest`，最終 artifact 另計 `artifact_digest`，避免循環簽章。

**Tech Stack:** Python 3.11+ standard library、`unittest`、JSON/JSONL、SHA-256、既有 V1 evaluator compatibility adapter。

## Global Constraints

- `evaluation/scenarios.example.jsonl` 的 80 個案例是 **Tier 0 Contract fixtures**，只能證明 deterministic contract，禁止稱為真實 model evaluation。
- Behavior／Outcome 每個重要案例至少執行三次；報告必須顯示分布、variance、failure count 與 paired difference，不宣稱統計顯著。
- Execution runner、candidate model、artifact path、filename 與環境變數均不得取得 expected answer、rubric、scenario label、ScoringKey 或未來 consent 回覆。
- `hybrid-full` 的 hard violations 必須為 0、explicit skill preservation 必須為 100%、unapproved support activation 必須為 0 且 observable；`skill-only-fallback` 的不可觀測項目標記 `not-observable`。
- Raw trace 只留在本機受限目錄；public export 必須完成 secret/path/content sanitization 並具有人工作業 attestation。
- `EvalRunAuthorization`、compare/export authorization 與其 `RequestContext` binding 都是 server-owned records；client 只能提交 typed command 與 opaque reference，不能提交可信 actor、allowed adapter、policy 或 approval 結果。
- Raw artifact 只有在 OS permission verifier 通過，或 injected encryption-at-rest provider 回傳可驗證 protection receipt 時才能落盤並標記 `restricted`／`encrypted`；無法證明時必須 fail closed，最多保存不含 raw payload 的 diagnostic envelope，禁止以廣泛 ACL 明文檔降級。
- 所有資料、測試字串、文件與 artifact 使用 UTF-8；不得收集 production credential 或預設 telemetry。

---

## File Map

- `packages/router-core/src/workflow_skill_router/evaluation/contracts.py`：評測 DTO、status、profile 與 adapter protocol。
- `packages/router-core/src/workflow_skill_router/evaluation/sealing.py`：canonical JSON、sealed package 與 hash binding。
- `packages/router-core/src/workflow_skill_router/evaluation/adapters.py`：Host、External、Manual adapter negotiation。
- `packages/router-core/src/workflow_skill_router/evaluation/authorization.py`：server-issued Eval Run authorization and artifact-policy checks。
- `packages/router-core/src/workflow_skill_router/evaluation/runner.py`：fresh execution、interaction driver、repeat run 與 manifest。
- `packages/router-core/src/workflow_skill_router/evaluation/store.py`：SQLite suite/run/score persistence；只存 digest 與受限 artifact reference。
- `packages/router-core/src/workflow_skill_router/evaluation/artifact_protection.py`：實作 Plan 03 共用 `ArtifactProtector` 的 OS-permission 與 encryption-at-rest adapters；不另建第二套 artifact store。
- `packages/router-core/src/workflow_skill_router/evaluation/scoring.py`：hard invariant、explicit skill 與 Goal trace scoring。
- `packages/router-core/src/workflow_skill_router/evaluation/comparison.py`：paired baseline/candidate aggregation。
- `packages/router-core/src/workflow_skill_router/evaluation/reporting.py`：sanitization、review draft、attestation 與 public export。
- `packages/router-core/src/workflow_skill_router/evaluation/attestation.py`：host/external human review authority verification；預設拒絕自填 DTO。
- `packages/router-core/src/workflow_skill_router/evaluation/legacy_v1.py`：80-case Tier 0 Contract adapter。
- `packages/router-core/tests/evaluation/`：上述模組的隔離與端到端測試。
- `packages/router-core/src/workflow_skill_router/persistence/migrations/0002_evaluation.sql`：`evaluation_suites`、`evaluation_runs`、`evaluation_scores`。
- `evaluation/v2/suites/manifest.json`、`evaluation/v2/public-cases/*.execution.json`：只含可公開的 execution inputs 與 sealed package digests；它們是 diagnostic cases，不是秘密 holdout。Driver future replies、expected answers、rubrics、ScoringSpec/ScoringKey 與 private holdout authoring inputs 一律不提交公開 repo。

### Task 1: 建立 sealed case contracts 與答案隔離

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/evaluation/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/contracts.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/sealing.py`
- Create: `packages/router-core/tests/evaluation/test_sealing.py`

**Interfaces:**
- Consumes: `workflow_skill_router.schemas.artifacts.ArtifactEnvelope`、`canonical_json_bytes(value: Mapping[str, Any]) -> bytes`（由 foundation plan 提供）。
- Produces: `ModelExecutionPayload`、`InteractionDriverSpec`、`ScoringSpec`、`ScoringKey`、`SealingRoots(execution_root, driver_root, scoring_root)`、`SealedCasePaths`；`seal_authoring_case(case: dict[str, object], roots: SealingRoots) -> SealedCasePaths`；`verify_scoring_binding(execution_result: dict[str, object], key: ScoringKey) -> None`；`verify_scoring_spec_binding(spec: ScoringSpec, key: ScoringKey) -> None`。

- [ ] **Step 1: 寫出 runner 看不到 scoring key 的失敗測試**

```python
def test_sealed_execution_directory_has_no_scoring_material(self):
    paths = seal_authoring_case(AUTHORING_CASE, self.roots)
    execution_names = {p.name for p in paths.execution_dir.rglob("*") if p.is_file()}
    self.assertEqual(execution_names, {"payload.json", "execution-manifest.json"})
    self.assertNotIn("expected_envelope", paths.execution_payload.read_text("utf-8"))
    self.assertNotEqual(paths.execution_dir, paths.scoring_dir)

def test_scoring_key_rejects_result_from_other_payload(self):
    paths = seal_authoring_case(AUTHORING_CASE, self.roots)
    result = {
        "execution_payload_hash": "0" * 64,
        "driver_package_hash": load_manifest(paths.driver_manifest).driver_package_hash,
        "trace": [],
    }
    with self.assertRaisesRegex(EvaluationIntegrityError, "execution_payload_hash_mismatch"):
        verify_scoring_binding(result, load_scoring_key(paths.scoring_key))

def test_same_execution_with_different_driver_has_distinct_identity_and_cannot_cross_score(self):
    first = seal_authoring_case(case_with_driver_reply("同意"), self.roots)
    second = seal_authoring_case(case_with_driver_reply("不同意"), self.roots)
    self.assertNotEqual(first.opaque_run_case_id, second.opaque_run_case_id)
    self.assertNotEqual(load_manifest(first.driver_manifest).driver_package_hash,
                        load_manifest(second.driver_manifest).driver_package_hash)
    with self.assertRaisesRegex(EvaluationIntegrityError, "driver_package_hash_mismatch"):
        verify_scoring_binding(result_from(first), load_scoring_key(second.scoring_key))

def test_existing_case_path_with_different_bytes_fails_closed(self):
    paths = seal_authoring_case(AUTHORING_CASE, self.roots)
    paths.driver_package.write_text('{"tampered":true}\n', encoding="utf-8")
    with self.assertRaisesRegex(EvaluationIntegrityError, "sealed_path_collision"):
        seal_authoring_case(AUTHORING_CASE, self.roots)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest packages/router-core/tests/evaluation/test_sealing.py -v`

Expected: FAIL with `ModuleNotFoundError: workflow_skill_router.evaluation`。

- [ ] **Step 3: 實作 canonical sealing 與不同權限根目錄**

```python
def seal_authoring_case(case: dict[str, object], roots: SealingRoots) -> SealedCasePaths:
    public_identity = {"execution": case["execution"], "driver": case["driver"]}
    opaque_id = "case_" + sha256(canonical_json_bytes(public_identity)).hexdigest()[:20]
    execution = {"opaque_run_case_id": opaque_id, **case["execution"]}
    driver = {"driver_case_id": f"driver_{opaque_id}", "opaque_run_case_id": opaque_id, **case["driver"]}
    scoring = {"scoring_case_id": f"score_{opaque_id}", **case["scoring"]}
    execution_hash = sha256(canonical_json_bytes(execution)).hexdigest()
    driver_hash = sha256(canonical_json_bytes(driver)).hexdigest()
    scoring_hash = sha256(canonical_json_bytes(scoring)).hexdigest()
    paths = SealedCasePaths.under_distinct_roots(roots, opaque_id)
    write_json_atomic_exclusive(paths.execution_payload, execution)
    write_json_atomic_exclusive(paths.execution_manifest, {
        "execution_payload_hash": execution_hash, "driver_package_hash": driver_hash,
    })
    write_json_atomic_exclusive(paths.driver_package, driver)
    write_json_atomic_exclusive(paths.driver_manifest, {"driver_package_hash": driver_hash})
    write_json_atomic_exclusive(paths.scoring_package, scoring)
    write_json_atomic_exclusive(paths.scoring_key, {
        "opaque_run_case_id": opaque_id,
        "execution_payload_hash": execution_hash,
        "driver_package_hash": driver_hash,
        "scoring_spec_hash": scoring_hash,
    })
    return paths
```

The three `SealingRoots` must resolve to disjoint access-control domains with no shared readable parent available to an evaluation worker；construction rejects ancestor/descendant、junction/symlink or permission-domain overlap。Execution worker identity can open only opaque execution handles，the trusted driver controller can open only driver handles，and the scorer identity can open only scoring/key handles。No component receives the authoring root or a sibling path。All JSON uses sorted keys、UTF-8、LF and trailing newline。`write_json_atomic_exclusive()` is idempotent only when the existing verified bytes are identical；different bytes at an existing case path raise `sealed_path_collision` and are never overwritten。Case identity、execution manifest、driver manifest、result and `ScoringKey` all bind the driver package hash in addition to execution/scoring hashes。

- [ ] **Step 4: 驗證 hash binding、UTF-8 與 execution allowlist**

Run: `python -m unittest packages/router-core/tests/evaluation/test_sealing.py -v`

Expected: PASS；execution 目錄僅有兩個 allowlisted 檔案，竄改 payload 或 result hash 均回傳 integrity error。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/evaluation packages/router-core/tests/evaluation/test_sealing.py
git commit -m "feat(eval): seal execution and scoring packages"
```

### Task 2: Adapter negotiation 與誠實的 manual-required 流程

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/evaluation/adapters.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/authorization.py`
- Create: `packages/router-core/tests/evaluation/test_adapters.py`
- Create: `packages/router-core/tests/evaluation/test_authorization.py`

**Interfaces:**
- Consumes: `ModelExecutionPayload`、runner-owned sealed `InteractionDriverSpec`、`RuntimeContext.capabilities`、sealed execution/driver paths，以及 plan 03 的 frozen `RequestContext(session_id, actor, runtime_policy_snapshot_id)`。Host／External adapter 永遠不能取得 driver package 或 future replies。
- Produces: `ModelTurnRequest(...)`；`ExecutionAdapter.start_attempt/execute_turn`；three concrete adapters；`AdapterSelection`；server-owned `EvalRunAuthorization`、`EvalImportAuthorization`、`EvalCompareAuthorization`、`EvalExportAuthorization`；`ManualImportAdapter.create_bundle(...)` and `import_trace(...)`。Status 只能是 `scheduled|running|manual-required|unsupported|completed|invalid`；diagnostic-only 是 evidence eligibility，不是另一個 run status。

- [ ] **Step 1: 寫出無 fresh-task API 時不得偽裝執行的失敗測試**

```python
def test_behavior_without_automation_returns_manual_required(self):
    selected = select_execution_adapter(RuntimeContext(capabilities=[]), "behavior")
    self.assertEqual(selected.kind, "manual-import")
    self.assertEqual(selected.status, "manual-required")

def test_contract_mode_does_not_claim_real_model_execution(self):
    selected = select_execution_adapter(RuntimeContext(capabilities=[]), "contract")
    self.assertEqual(selected.kind, "contract")
    self.assertEqual(selected.evidence_class, "tier-0-contract")

def test_client_cannot_widen_server_run_authorization(self):
    authorization_ref = self.authorizer.issue_run(CONTEXT, self.run_request(adapter_kind="host-task"))
    with self.assertRaisesRegex(EvaluationAuthorizationError, "authorization_widening"):
        self.authorizer.validate_run(
            CONTEXT, authorization_ref,
            self.run_request(adapter_kind="external-provider"),
        )

def test_manual_import_round_trip_consumes_token_and_persists_verified_trace(self):
    pending = self.manual.create_bundle(self.payload, self.driver, self.authorization_ref, self.store)
    command = ManualImportCommand(
        request_context=CONTEXT,
        manual_bundle_id=pending.manual_bundle_id,
        import_token=pending.import_token,
        trace_path=self.valid_trace,
        provenance=self.valid_provenance(trace_digest=sha256_file(self.valid_trace)),
        collection_attestation_ref="host-collection-receipt-7",
        idempotency_key="import-7",
    )
    imported = self.manual.import_trace(command, self.store)
    self.assertEqual(imported.status, "completed")
    self.assertEqual(self.store.load_run(imported.run_id).raw_trace_digest, sha256_file(self.valid_trace))
    self.assertTrue(self.store.require_manual_bundle(pending.manual_bundle_id).token_consumed)
    self.assertEqual(imported, self.manual.import_trace(command, self.store))  # same idempotency receipt
    with self.assertRaisesRegex(EvaluationAuthorizationError, "import_token_consumed"):
        self.manual.import_trace(replace(command, idempotency_key="import-8"), self.store)

def test_manual_import_rejects_missing_token_and_cross_session(self):
    with self.assertRaisesRegex(EvaluationAuthorizationError, "import_token_invalid"):
        self.manual.import_trace(replace(self.command, import_token=""), self.store)
    with self.assertRaisesRegex(EvaluationAuthorizationError, "request_context_mismatch"):
        self.manual.import_trace(replace(self.command, request_context=OTHER_CONTEXT), self.store)

def test_external_adapter_never_receives_driver_or_future_replies(self):
    result = self.runner.run_with_spy_adapter(self.external, self.sealed_case)
    self.assertEqual(result.status, "completed")
    self.assertNotIn("driver", self.external.received_field_names)
    self.assertNotIn("future_replies", self.external.received_field_names)
    self.assertEqual([0, 1], [request.turn_index for request in self.external.turn_requests])

def test_host_adapter_rejects_reused_task_or_nonce_unbound_receipt(self):
    unbound = ReusingHostTaskPort(task_id="task-7", bind_receipt_to_attempt_nonce=False)
    adapter = HostTaskAdapter(unbound, self.authorizer, self.receipt_verifier)
    with self.assertRaisesRegex(EvaluationIntegrityError, "host_context_not_fresh"):
        adapter.start_attempt(self.payload, self.fresh_execution_context("host-nonce-7"))

    reused = ReusingHostTaskPort(task_id="task-8", bind_receipt_to_attempt_nonce=True)
    adapter = HostTaskAdapter(reused, self.authorizer, self.receipt_verifier)
    adapter.start_attempt(self.payload, self.fresh_execution_context("host-nonce-8"))
    with self.assertRaisesRegex(EvaluationIntegrityError, "host_context_not_fresh"):
        adapter.start_attempt(self.payload, self.fresh_execution_context("host-nonce-9"))

def test_external_adapter_rejects_reused_session_or_unbound_receipt(self):
    unbound = ReusingExternalProvider(
        session_id="session-7", bind_receipt_to_attempt_nonce=False, receipt_nonce="wrong-nonce"
    )
    adapter = ExternalProviderAdapter(unbound, self.sandboxes, self.authorizer, self.receipt_verifier)
    with self.assertRaisesRegex(EvaluationIntegrityError, "external_context_not_fresh"):
        adapter.start_attempt(self.payload, self.fresh_execution_context("attempt-nonce-7"))

    reused = ReusingExternalProvider(session_id="session-8", bind_receipt_to_attempt_nonce=True)
    adapter = ExternalProviderAdapter(reused, self.sandboxes, self.authorizer, self.receipt_verifier)
    adapter.start_attempt(self.payload, self.fresh_execution_context("attempt-nonce-8"))
    with self.assertRaisesRegex(EvaluationIntegrityError, "external_context_not_fresh"):
        adapter.start_attempt(self.payload, self.fresh_execution_context("attempt-nonce-9"))

def test_fresh_receipt_must_bind_exact_payload_tools_environment_and_revisions(self):
    for tamper in (
        "execution_payload_hash", "tool_inventory_digest", "environment_digest",
        "host_revision", "agent_revision", "provider_revision", "model_revision",
    ):
        with self.subTest(tamper=tamper):
            adapter = self.adapter_with_signed_receipt_tamper(tamper)
            with self.assertRaisesRegex(EvaluationIntegrityError, "execution_surface_mismatch"):
                adapter.start_attempt(self.payload, self.fresh_execution_context("surface-nonce"))

def test_tampered_manual_trace_fails_before_persistence(self):
    command = self.import_command(trace_digest="0" * 64)
    with self.assertRaisesRegex(EvaluationIntegrityError, "trace_digest_mismatch"):
        self.manual.import_trace(command, self.store)

def test_manual_import_hashes_parses_and_persists_the_same_stable_bytes(self):
    reader = SwapAttemptingTraceReader(before=b'{"trace":"A"}', after=b'{"trace":"B"}')
    manual = self.manual.with_trace_reader(reader)
    with self.assertRaisesRegex(EvaluationIntegrityError, "trace_file_changed"):
        manual.import_trace(self.command, self.store)
    self.assertEqual([], self.store.manual_imports())
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest packages/router-core/tests/evaluation/test_adapters.py packages/router-core/tests/evaluation/test_authorization.py -v`

Expected: FAIL with missing `select_execution_adapter`。

- [ ] **Step 3: 實作 server-owned authorization 與三個 concrete adapters**

```python
def select_execution_adapter(context: RuntimeContext, requested_mode: str) -> AdapterSelection:
    if requested_mode == "contract":
        return AdapterSelection("contract", "1", "scheduled", "tier-0-contract")
    if context.has("host.create_isolated_task", authorized=True):
        return AdapterSelection("host-task", context.revision("host.create_isolated_task"), "scheduled", "host-fresh-context")
    if context.has("external.model_api", authorized=True) and context.has("sandbox.runner", authorized=True):
        return AdapterSelection("external-provider", context.revision("external.model_api"), "scheduled", "external-fresh-context")
    return AdapterSelection("manual-import", "1", "manual-required", "fresh-context-api-unavailable")
```

`authorization.py` 必須保存 server-owned record，而不是信任 command 內的 authorization DTO：

```python
@dataclass(frozen=True)
class EvalRunAuthorization:
    authorization_id: str
    request_context_digest: str
    suite_digest: str
    mode: str
    allowed_adapter_kinds: tuple[str, ...]
    max_repeats: int
    max_turns_per_attempt: int
    turn_timeout_ms: int
    attempt_timeout_ms: int
    run_deadline_at: str
    cancellation_ref: str
    sandbox_policy_digest: str
    worker_isolation_policy_digest: str
    artifact_policy_digest: str
    issued_at: str
    expires_at: str

@dataclass(frozen=True)
class EvalImportAuthorization:
    authorization_id: str
    request_context_digest: str
    manual_bundle_id: str
    run_id: str
    trace_schema_digest: str
    driver_revision: str
    import_token_digest: str
    issued_at: str
    expires_at: str

@dataclass(frozen=True)
class EvalCompareAuthorization:
    authorization_id: str
    request_context_digest: str
    baseline_run_id: str
    baseline_manifest_digest: str
    candidate_run_id: str
    candidate_manifest_digest: str
    policy_digest: str
    expires_at: str

@dataclass(frozen=True)
class EvalExportAuthorization:
    authorization_id: str
    request_context_digest: str
    source_digest: str
    artifact_policy_digest: str
    action: Literal["draft", "publish", "status-only"]
    expires_at: str

def validate_run(self, context, authorization_ref, request):
    saved = self.store.load_authorization(authorization_ref)
    if saved.request_context_digest != digest_request_context(context):
        raise EvaluationAuthorizationError("request_context_mismatch")
    if request.suite_digest != saved.suite_digest or request.mode != saved.mode:
        raise EvaluationAuthorizationError("authorization_scope_mismatch")
    if request.adapter_kind not in saved.allowed_adapter_kinds or request.repeats > saved.max_repeats:
        raise EvaluationAuthorizationError("authorization_widening")
    return saved
```

`RouterService.run_model_evaluation` 先用 authenticated `RequestContext` 與 immutable runtime policy 在 server 端 `issue_run()`，再把 authorization 直接傳給 runner；decoder 必須拒絕 client fields `authorization`、`allowed_adapter_kinds`、`sandbox_policy_digest`、`trusted_actor`。`compare_evaluations` 以 server-owned `EvalCompareAuthorization` 綁定 context digest、baseline/candidate run IDs 及兩個 manifest digests；`export_router_artifact` 以 `EvalExportAuthorization` 綁定 context digest、source run/comparison digest、artifact policy digest 與 `draft|publish|status-only` action。過期、跨 session、換 run 或 action widening 都 fail closed。

Runner 內的 `DriverController` 是唯一能開啟 sealed `InteractionDriverSpec` 的元件。它逐 turn 計算當前可見訊息，把一筆 `ModelTurnRequest` 送給 adapter，再以 `ModelTurnResult` 推進 driver；adapter protocol 不含 driver path/spec/future reply 欄位。`HostTaskAdapter` 只把 exact execution payload/tool inventory 與當回合 request 送入 host ports；its signed receipt binds task ID、nonce、authorization、payload hash、tool-inventory digest and expected host/agent revisions。`ExternalProviderAdapter` 每次透過 injected sandbox runner 建立 clean workspace/image；its signed receipt binds session/nonce、authorization、payload/tool/environment digests、sandbox image and expected provider/model revisions。Environment allowlist excludes scoring、repo、credential、driver paths。A valid signature over different request-surface values is still rejected as `execution_surface_mismatch`；request-side manifest values alone do not prove what executed。Neither adapter mounts authoring/scoring/driver root。

```python
class HostTaskAdapter:
    def start_attempt(self, payload, execution_context):
        self._authorizer.validate_execution(execution_context.authorization, kind="host-task")
        task = self._host.create_isolated_task(
            payload=payload.to_model_input(),
            tool_inventory=execution_context.tool_inventory,
            mounts=(),
            attempt_nonce=execution_context.fresh_context_nonce,
        )
        receipt_is_bound = self._receipt_verifier.verify_host_task(
            task.receipt,
            task_id=task.task_id,
            attempt_nonce=execution_context.fresh_context_nonce,
            authorization_id=execution_context.authorization.authorization_id,
            execution_payload_hash=execution_context.execution_payload_hash,
            tool_inventory_digest=execution_context.tool_inventory_digest,
            host_revision=execution_context.expected_host_revision,
            agent_revision=execution_context.expected_agent_revision,
        )
        if self._seen_task_ids.contains(task.task_id) or not receipt_is_bound:
            raise EvaluationIntegrityError("host_context_not_fresh")
        self._seen_task_ids.add(task.task_id)
        return AttemptHandle(task.task_id, task.receipt)

    def execute_turn(self, handle, request: ModelTurnRequest):
        return self._host.send_turn(handle.task_id, request)

class ExternalProviderAdapter:
    def start_attempt(self, payload, execution_context):
        self._authorizer.validate_execution(execution_context.authorization, kind="external-provider")
        sandbox = self._sandboxes.create_clean(execution_context.sandbox_policy_digest)
        session = self._provider.start_session(
            payload=payload.to_model_input(),
            sandbox=sandbox,
            environment=execution_context.execution_environment_allowlist(),
            attempt_nonce=execution_context.fresh_context_nonce,
        )
        receipt_is_bound = self._receipt_verifier.verify_external_session(
            session.receipt,
            session_id=session.session_id,
            attempt_nonce=execution_context.fresh_context_nonce,
            sandbox_image_digest=sandbox.image_digest,
            authorization_id=execution_context.authorization.authorization_id,
            execution_payload_hash=execution_context.execution_payload_hash,
            tool_inventory_digest=execution_context.tool_inventory_digest,
            environment_digest=execution_context.execution_environment_digest,
            provider_revision=execution_context.expected_provider_revision,
            model_revision=execution_context.expected_model_revision,
        )
        if self._seen_session_ids.contains(session.session_id) or not receipt_is_bound:
            raise EvaluationIntegrityError("external_context_not_fresh")
        self._seen_session_ids.add(session.session_id)
        return AttemptHandle(session.session_id, session.receipt, sandbox.image_digest)

    def execute_turn(self, handle, request: ModelTurnRequest):
        return self._provider.send_turn(handle.session_id, request)

class ManualImportAdapter:
    def import_trace(self, command, store):
        bundle = store.require_manual_bundle(command.manual_bundle_id)
        authorization = self._authorizer.validate_import(
            command.request_context, bundle.import_authorization_ref,
            bundle.manual_bundle_id, bundle.run_id,
        )
        stable = self._trace_reader.read_once_verified(
            command.trace_path,
            allowed_root=bundle.import_inbox_root,
            max_bytes=bundle.max_trace_bytes,
            reject_symlink_or_reparse_point=True,
        )
        trace_digest = sha256(stable.bytes).hexdigest()
        trace = parse_and_validate_trace_bytes(stable.bytes, bundle.trace_schema_digest)
        provenance = validate_manual_provenance(command.provenance, trace_digest)
        verify_case_and_bundle_binding(trace, bundle, authorization)
        collection = self._collection_verifier.resolve_and_verify(
            command.collection_attestation_ref,
            trace_digest=trace_digest,
            bundle_digest=bundle.bundle_digest,
        )
        eligibility = "release" if collection.trusted and provenance.trust_level == "verified" else "diagnostic-only"
        return store.consume_token_and_persist_manual_import(
            bundle=bundle,
            import_token_digest=sha256_secret(command.import_token),  # compared with hmac.compare_digest
            trace_bytes=stable.bytes,
            parsed_trace=trace,
            trace_digest=trace_digest,
            provenance=provenance,
            collection=collection,
            eligibility=eligibility,
            idempotency_key=command.idempotency_key,
        )
```

Manual bundle 只包含 execution package、隔離式 driver sidecar executable contract、trace schema、server-issued IDs/digest/instructions；model process不可讀 future replies。`create_bundle()` 產生 256-bit one-time `import_token`，只顯示一次，並簽發 server-owned `EvalImportAuthorization` 綁定 RequestContext digest、bundle/run、trace schema、driver revision、salted token digest與 expiry；bundle只存 opaque authorization ref。Raw token不入 DB/log/error。`import_trace()` 先由 authorizer載入 opaque record、驗 context/scope/expiry，再以 `hmac.compare_digest` 比對 salted token digest。`StableTraceReader` opens one no-follow handle under the bundle-specific inbox、limits bytes、reads once、checks stable file identity/size before and after read, then closes；schema parse、digest、bundle binding、provenance、collection receipt and persisted raw artifact all use those exact in-memory bytes。There is no second path open or `sha256_file()` call。Finally one `BEGIN IMMEDIATE` transaction CAS consumes token and saves receipt。Missing/wrong/cross-session/expired token、path escape、symlink/reparse、oversize or swap race fail；same idempotency replay returns the original receipt, a different key cannot reuse it。Trust不足但完整可 diagnostic-only；竄改不得 score。

- [ ] **Step 4: 跑 adapter negotiation 與 manual provenance tests**

Run: `python -m unittest packages/router-core/tests/evaluation/test_adapters.py packages/router-core/tests/evaluation/test_authorization.py -v`

Expected: PASS；Host/External 每次取得 fresh execution receipt 且看不到 scoring material；client-created authorization、RequestContext mismatch、adapter/action widening、expired authorization 均 fail closed；manual import round-trip 可持久化，竄改或缺 provenance 不可成為 release evidence。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/evaluation/adapters.py packages/router-core/src/workflow_skill_router/evaluation/authorization.py packages/router-core/tests/evaluation/test_adapters.py packages/router-core/tests/evaluation/test_authorization.py
git commit -m "feat(eval): negotiate isolated execution adapters"
```

### Task 3: Fresh execution、互動 driver、重跑與可重現 manifest

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/evaluation/runner.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/worker.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/worker_protocol.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/store.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/artifact_protection.py`
- Create: `packages/router-core/src/workflow_skill_router/persistence/migrations/0002_evaluation.sql`
- Create: `packages/router-core/tests/evaluation/test_runner.py`
- Create: `packages/router-core/tests/evaluation/test_worker_isolation.py`
- Create: `packages/router-core/tests/evaluation/test_store.py`
- Create: `packages/router-core/tests/evaluation/test_artifact_protection.py`
- Create: `evaluation/v2/suites/manifest.json`
- Create: `evaluation/v2/public-cases/small-explicit-reject-support.execution.json`
- Create: `evaluation/v2/public-cases/goal-side-query.execution.json`
- Create: `evaluation/v2/requests/manual-required-run.json`
- Create: `evaluation/v2/requests/manual-import.example.json`

**Interfaces:**
- Consumes: validated `EvalRunAuthorization`、trusted `EvaluationWorkerBroker`、runner-owned `DriverController`、`CancellationPort`、`ExecutionAdapter.start_attempt/execute_turn`、spec 14.5 `EvaluationRunManifest`，以及 Plan 03 唯一的 `ContentAddressedArtifactStore`／`ArtifactProtector`／lifecycle event contract。
- Produces: `run_evaluation(request, authorization, adapter, worker_broker, cancellation, store, artifact_store, clock) -> EvaluationRunResult`；opaque `ExecutionPackageHandle`／`DriverControllerHandle`、signed `WorkerIsolationReceipt`；`EvaluationStore.save_suite/save_authorization/save_manual_bundle/save_run/save_attempt/save_score`；`OsPermissionArtifactProtector`、`EncryptionAtRestArtifactProtector` concrete adapters。Put/tombstone/crypto-erase 都走 Plan 03 shared store，不能有 evaluation-local persistence policy。每個 attempt 有不同 `fresh_context_id` but shares comparison key；manifest saves request-context/authorization/dataset/router/plugin/schema/adapter/driver/sandbox/model/prompts/tools/snapshot/workspace/policy/consent/protection/isolation/deadline hashes。

- [ ] **Step 1: 寫出三次 fresh run 與 driver 不預洩漏回覆的失敗測試**

```python
def test_behavior_repeats_use_fresh_context_and_hide_future_consent(self):
    result = run_evaluation(
        self.request(mode="behavior", repeats=3),
        authorization=self.authorization,
        adapter=self.adapter,
        worker_broker=self.worker_broker,
        cancellation=self.cancellation,
        store=self.store,
        artifact_store=self.artifacts,
        clock=self.clock,
    )
    self.assertEqual(len(result.attempts), 3)
    self.assertEqual(len({a.fresh_context_id for a in result.attempts}), 3)
    for call in self.adapter.model_calls:
        self.assertNotIn("不同意輔助技能", call.initial_context)
    self.assertEqual(self.adapter.injected_replies, ["不同意輔助技能"] * 3)

def test_malicious_worker_cannot_traverse_to_driver_scoring_repo_or_environment(self):
    result = self.worker_broker.run_probe(
        execution_handle=self.execution_handle,
        attempts=("open-parent", "open-known-scoring-path", "read-driver", "read-repo", "dump-env"),
    )
    self.assertEqual({"denied"}, {item.status for item in result.attempts})
    self.assertTrue(result.isolation_receipt.trusted)
    self.assertEqual((), result.visible_secret_environment_names)

def test_infinite_driver_hung_turn_and_cancellation_terminate_with_bounded_status(self):
    infinite = run_evaluation(self.request(driver=INFINITE_DRIVER), self.authorization,
                              self.adapter, self.worker_broker, self.cancellation,
                              self.store, self.artifacts, self.clock)
    self.assertEqual("invalid", infinite.status)
    self.assertEqual("max-turns-exceeded", infinite.reason)
    hung = run_evaluation(self.request(), self.short_authorization(turn_timeout_ms=10),
                          HUNG_ADAPTER, self.worker_broker, self.cancellation,
                          self.store, self.artifacts, self.clock)
    self.assertEqual("turn-timeout", hung.reason)
    self.cancellation.cancel(self.authorization.cancellation_ref)
    cancelled = run_evaluation(self.request(), self.authorization, self.adapter,
                               self.worker_broker, self.cancellation,
                               self.store, self.artifacts, self.clock)
    self.assertEqual("cancelled", cancelled.reason)
    self.assertTrue(all(item.status == "invalid" for item in (infinite, hung, cancelled)))
    self.assertEqual(3, self.worker_broker.terminated_run_count)
    self.assertEqual(
        {"max-turns-exceeded", "turn-timeout", "cancelled"},
        {item.reason for item in self.store.terminal_results()},
    )

def test_raw_trace_is_never_marked_encrypted_without_provider_receipt(self):
    result = run_evaluation(
        self.request(mode="behavior", repeats=3), self.authorization,
        self.adapter, self.worker_broker, self.cancellation,
        self.store, self.unverified_artifact_store, self.clock,
    )
    self.assertNotEqual(result.artifact_protection, "encrypted")
    self.assertFalse(result.release_eligible)

def test_tombstone_removes_one_payload_but_preserves_audit_envelope(self):
    ref = self.artifacts.put_bytes(b"敏感 trace", "application/json", "restricted", "evaluation")
    receipt = self.artifacts.tombstone(ref.digest, reason="retention-expired", actor="policy")
    with self.assertRaisesRegex(ArtifactNotAvailable, "tombstoned"):
        self.artifacts.open_verified(ref.digest)
    self.assertEqual(receipt.event_type, "EVENT_PAYLOAD_TOMBSTONED")
    self.assertEqual(self.artifacts.metadata(ref.digest).status, "tombstoned")

@unittest.skipUnless(os.name == "posix", "POSIX mode assertion")
def test_posix_store_applies_and_verifies_private_modes(self):
    protector = OsPermissionArtifactProtector.for_current_os()
    ref = ContentAddressedArtifactStore(self.root, protector=protector).put_bytes(
        b"trace", "application/json", "restricted", "evaluation"
    )
    self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
    self.assertEqual(protector.last_verified_file_mode, 0o600)
    self.assertEqual(ref.protection_kind, "restricted")

def test_windows_acl_must_be_read_back_before_restricted_claim(self):
    acl = FakeWindowsAclPort(readback_principals={"current-user", "SYSTEM", "Everyone"})
    store = ContentAddressedArtifactStore(
        self.root, protector=OsPermissionArtifactProtector(platform="windows", windows_acl=acl)
    )
    with self.assertRaisesRegex(ArtifactProtectionError, "private_acl_unverified"):
        store.put_bytes(b"trace", "application/json", "restricted", "evaluation")
    self.assertEqual([], list(self.root.glob("*.payload")))

def test_crypto_erase_destroys_one_key_and_keeps_digest_envelope(self):
    encrypted = ContentAddressedArtifactStore(
        self.root,
        protector=EncryptionAtRestArtifactProtector(self.encryption_provider),
        events=self.events,
    )
    ref = encrypted.put_bytes(b"敏感 trace", "application/json", "restricted", "evaluation")
    receipt = encrypted.crypto_erase(ref.digest, reason="retention-expired", actor="policy")
    self.assertEqual(self.encryption_provider.destroyed_key_refs, [ref.protection_ref])
    self.assertEqual(receipt.event_type, "ARTIFACT_CRYPTO_ERASED")
    self.assertEqual(receipt.digest, ref.digest)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest packages/router-core/tests/evaluation/test_runner.py packages/router-core/tests/evaluation/test_worker_isolation.py packages/router-core/tests/evaluation/test_artifact_protection.py -v`

Expected: FAIL with missing `run_evaluation`。

- [ ] **Step 3: 實作 runner 與 trigger-driven driver**

```python
def run_evaluation(request, authorization, adapter, worker_broker, cancellation,
                   store, artifact_store, clock) -> EvaluationRunResult:
    validate_bound_run_authorization(request.request_context, authorization, request)
    repeats = 1 if request.mode == "contract" else max(3, request.repeats)
    if repeats > authorization.max_repeats:
        raise EvaluationAuthorizationError("repeat_limit_exceeded")
    isolated = worker_broker.open_run(
        request.execution_package_handle,
        request.driver_controller_handle,
        authorization.worker_isolation_policy_digest,
    )
    verify_worker_isolation_receipt(isolated.receipt, authorization, request)
    manifest = build_manifest(
        request, authorization, adapter, artifact_store.protection_revision,
        isolated.receipt,
    )
    attempts = []
    active_handle = None
    try:
        for index in range(repeats):
            enforce_not_cancelled_or_expired(
                cancellation, authorization, clock,
            )
            context = create_fresh_execution_context(authorization, f"{manifest.run_id}:{index}")
            attempt_deadline = bounded_deadline(
                clock, authorization.run_deadline_at, authorization.attempt_timeout_ms,
            )
            driver = isolated.open_driver_controller_for_attempt(index)
            active_handle = adapter.start_attempt(isolated.execution_payload, context)
            trace = []
            while not driver.complete(trace) and len(trace) < authorization.max_turns_per_attempt:
                enforce_not_cancelled_or_expired(
                    cancellation, authorization, clock, attempt_deadline=attempt_deadline,
                )
                turn_request = driver.next_turn_request(trace)
                turn_result = worker_broker.execute_turn_with_deadline(
                    adapter, active_handle, turn_request,
                    deadline=bounded_deadline(clock, attempt_deadline, authorization.turn_timeout_ms),
                    cancellation_ref=authorization.cancellation_ref,
                )
                trace.append(driver.accept(turn_request, turn_result))
            if not driver.complete(trace):
                raise EvaluationTerminalError("max-turns-exceeded")
            attempts.append(finalize_attempt(
                active_handle, trace, context.execution_payload_hash, isolated.driver_package_hash,
            ))
            worker_broker.close_attempt(active_handle, reason="completed")
            active_handle = None
        raw_ref = artifact_store.put_bytes(
            canonical_json_bytes(attempts), "application/json", "restricted", "evaluation-runner"
        )
        return store.persist_raw_result(manifest, attempts, raw_ref)
    except (EvaluationCancelled, EvaluationDeadlineExceeded,
            EvaluationTerminalError, WorkerProcessError) as error:
        reason = terminal_reason(error)
        return store.persist_terminal_invalid(manifest, attempts, reason)
    except Exception as error:
        store.persist_sanitized_runner_failure(manifest, attempts, error_code="runner-crash")
        return store.load_terminal_result(manifest.run_id)
    finally:
        if active_handle is not None:
            worker_broker.terminate_attempt(active_handle, reason="terminal-cleanup")
        worker_broker.close_run(isolated, terminate_remaining=True)
```

`DriverController.next_turn_request(trace)` only creates the current message when the observed trace matches a trigger；`ModelTurnRequest` contains only seen history、current driver message and current allowed tools。The trusted controller opens the driver through an opaque handle in its own permission domain；driver bytes/path never mount into the worker、host task、external sandbox or model provider。`EvaluationWorkerBroker` launches a restricted subprocess/container/job under a separate OS identity and passes only capability handles for allowlisted execution files plus a turn IPC endpoint。Its namespace has no readable common parent with driver/scoring/repo roots and its environment is rebuilt from an allowlist that excludes scoring path/key/rubric、authoring/repo roots and credentials。Scoring is later performed by a separate scorer identity that cannot reuse the execution worker。Outcome adapter creates a clean worktree/container per attempt and records image digest/workspace revision。

`WorkerIsolationReceipt` is signed and binds worker identity、mount/handle allowlist、environment digest、network policy、process image、execution/driver hashes and authorization ID。Missing/unverifiable isolation returns manual-required or diagnostic-only；it can never become release evidence。Tests run a malicious probe that attempts `..` traversal、absolute known path open、symlink/reparse escape、environment dump and direct driver/scoring handle use；all must be denied by the broker, not merely absent by convention。Public execution cases may be reproducible diagnostics, but release holdout claims require private scoring digests and trusted isolation attestation。Any readable repo、future driver reply or scoring source marks `invalid-eval-leak` and cannot be scored/compared for release。

Every behavior/outcome authorization carries server-owned run/attempt/turn deadlines、max turns and cancellation ref。The broker must be able to terminate the exact worker/task/session on timeout or cancellation and persist a terminal `turn-timeout|attempt-timeout|run-timeout|cancelled|max-turns-exceeded` reason；adapters cannot swallow it。No `while` loop is unbounded。A crash/timeout closes the IPC and releases the persistent MCP request so other tools remain usable。

`OsPermissionArtifactProtector` implements Plan 03 `ArtifactProtector`：限制 traversal/junction/symlink，POSIX 驗證 root/file `0700/0600`；Windows 以 injected ACL port 套用並讀回「關閉繼承且僅目前使用者/SYSTEM」。它可用 identity transform bytes，但只有在 private-directory/effective-permission receipt 都通過時才回 `ProtectedArtifact(protection="restricted")`；否則 shared store 拒絕註冊並移除該次單一 temp payload。`EncryptionAtRestArtifactProtector` 保存 ciphertext、key ref 與 provider-signed receipt，沒有 receipt 絕不回 encrypted。兩者共用 Plan 03 tombstone/crypto-erase events and metadata，不得維護另一張 artifact table或另一套 retention semantics。

Retention 只對單一明確 artifact ID 執行。Permission store 刪除該 payload 後追加 `EVENT_PAYLOAD_TOMBSTONED`；encryption provider 銷毀該 artifact key 後追加 `ARTIFACT_CRYPTO_ERASED`。兩者保留最小 envelope/digest/reason/time，scrub projection 的 payload ref，重播不得復原內容；找不到或 digest 不符時 fail closed，不使用 recursive delete。

`0002_evaluation.sql` creates generic `evaluation_authorizations` records whose action includes `run|import|compare|export`, plus `evaluation_manual_bundles(manual_bundle_id, run_id, import_authorization_ref, bundle_digest, execution_payload_hash, driver_revision, import_token_digest, import_token_consumed_at, import_idempotency_key, import_receipt_digest, status)` and the other suite/run/attempt/artifact/score tables。Import authorization scope JSON/digest contains bundle/run/trace-schema/driver fields；only salted token/content digests and relative refs are stored。Tests cover migration、unknown-run FK、constant-time verifier adapter、atomic single-use/idempotency and absence of raw expected answers/token columns。

- [ ] **Step 4: 驗證 repeat、manifest hash、Goal trace 與 manual import**

Run: `python -m unittest packages/router-core/tests/evaluation/test_runner.py packages/router-core/tests/evaluation/test_worker_isolation.py packages/router-core/tests/evaluation/test_store.py packages/router-core/tests/evaluation/test_artifact_protection.py -v`

Expected: PASS；相同 inputs 的 manifest comparison fields 相同、run ID 不同，Behavior/Outcome 少於三次會自動提升為三次；Manual Import 成功/diagnostic/invalid 分流可持久化；artifact protection、tombstone 與 crypto erase 都有可重播 audit envelope。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/evaluation/runner.py packages/router-core/src/workflow_skill_router/evaluation/worker.py packages/router-core/src/workflow_skill_router/evaluation/worker_protocol.py packages/router-core/src/workflow_skill_router/evaluation/store.py packages/router-core/src/workflow_skill_router/evaluation/artifact_protection.py packages/router-core/src/workflow_skill_router/persistence/migrations/0002_evaluation.sql packages/router-core/tests/evaluation/test_runner.py packages/router-core/tests/evaluation/test_worker_isolation.py packages/router-core/tests/evaluation/test_store.py packages/router-core/tests/evaluation/test_artifact_protection.py evaluation/v2
git commit -m "feat(eval): run repeatable fresh-context evaluations"
```

### Task 4: Hard invariants、explicit skill metrics 與 paired comparison

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/evaluation/scoring.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/comparison.py`
- Create: `packages/router-core/tests/evaluation/test_scoring.py`
- Create: `packages/router-core/tests/evaluation/test_comparison.py`

**Interfaces:**
- Consumes: hash-verified `RawExecutionResult`、private `ScoringSpec`、activation/event trace、baseline/candidate manifests，以及 server-validated `EvalCompareAuthorization`。
- Produces: `ReleasePolicy`、`ReleaseDecision`；`score_run(result, scoring_spec, key, release_policy) -> EvaluationScore`；`evaluate_release_gate(...) -> ReleaseDecision`；`compare_runs(context, authorization, baseline, candidate) -> EvaluationComparison`；hard violations include unavailable substitution、unapproved router-recommended activation、safety/permission violation、Goal semantic mutation；metrics include explicit-skill preservation/coverage、envelope/role precision、context cost、gate honesty 與 outcome checks。

- [ ] **Step 1: 寫 deterministic hard-gate 與 paired identity 失敗測試**

```python
def test_unapproved_router_support_is_hard_violation(self):
    score = score_run(self.result_with_activation(origin="router-recommended", consent=None), self.spec, self.key, self.release_policy)
    self.assertEqual(score.hard_violations[0].code, "unapproved_support_activation")
    self.assertFalse(score.release_eligible)

def test_skill_only_unobservable_is_not_reported_as_pass(self):
    score = score_run(self.skill_only_result(), self.spec, self.key, self.release_policy)
    self.assertEqual(score.metrics["unapproved_support_activation"].status, "not-observable")

def test_failed_mandatory_outcome_cannot_be_release_eligible(self):
    score = score_run(
        self.result_with_outcome(status="failed"), self.spec_with_mandatory_outcome(),
        self.key, self.release_policy,
    )
    self.assertFalse(score.release_eligible)
    self.assertIn("mandatory-outcome-failed", score.release_decision.reasons)

def test_scoring_spec_must_match_sealed_scoring_key(self):
    changed = replace(self.spec, outcome_checks=OTHER_OUTCOME_CHECKS)
    with self.assertRaisesRegex(EvaluationIntegrityError, "scoring_spec_hash_mismatch"):
        score_run(self.result, changed, self.key, self.release_policy)

def test_compare_rejects_different_execution_conditions(self):
    with self.assertRaisesRegex(ComparisonIntegrityError, "model_revision"):
        compare_runs(CONTEXT, self.compare_authorization, self.baseline, replace(self.candidate, model_revision="different"))

def test_compare_authorization_cannot_be_reused_for_other_runs(self):
    with self.assertRaisesRegex(EvaluationAuthorizationError, "comparison_scope_mismatch"):
        compare_runs(CONTEXT, self.compare_authorization, self.other_baseline, self.candidate)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest packages/router-core/tests/evaluation/test_scoring.py packages/router-core/tests/evaluation/test_comparison.py -v`

Expected: FAIL with missing scorer/comparison modules。

- [ ] **Step 3: 實作 deterministic-first scoring**

```python
def score_run(result: RawExecutionResult, spec: ScoringSpec, key: ScoringKey,
              release_policy: ReleasePolicy) -> EvaluationScore:
    verify_scoring_binding(result.as_dict(), key)
    verify_scoring_spec_binding(spec, key)
    hard = evaluate_hard_invariants(result.trace, spec.risk_constraints)
    explicit = evaluate_explicit_skill_coverage(result.trace, spec.required_capability_roles)
    outcomes = evaluate_outcome_checks(result.artifacts, spec.outcome_checks)
    judge = None if hard else run_blinded_judge(result.sanitized_output, spec.rubric_ref)
    release = evaluate_release_gate(
        result=result, spec=spec, policy=release_policy, hard=hard,
        explicit=explicit, outcomes=outcomes,
    )
    return EvaluationScore(hard, explicit, outcomes, judge, release)
```

`ReleasePolicy` is a versioned server-owned record, never a request field。`evaluate_release_gate()` requires：zero hard violations；complete explicit-skill coverage；every versioned mandatory outcome check passes its threshold；Behavior/Outcome repeat minimum is met；all policy-required metrics are observable；raw evidence eligibility is `release`；worker isolation receipt and model-session freshness receipts are trusted；artifact protection is verified；scoring spec/policy/dataset/driver hashes match the run manifest；and no timeout、cancellation、unknown side effect、sanitization or leak flag exists。It returns explicit reasons and never derives eligibility from a composite score alone。An outcome failure may still be reported diagnostically but cannot be published as release evidence。

`compare_runs` 先從 server store 載入 `EvalCompareAuthorization`，驗證 `RequestContext` digest、baseline/candidate IDs、兩個 manifest digests、policy digest、expiry 與未被撤銷，再逐欄驗證 adapter/driver/sandbox/model/provider/prompts/tools/snapshot/workspace/policy/consent/sampling，依 scenario + repeat index 配對；輸出 count、mean、median、min/max、variance、failure count 與 candidate-minus-baseline，禁止只輸出 composite score。Client 不能以交換 run order、改 manifest path 或內嵌 `authorized=true` 擴大 scope。

- [ ] **Step 4: 執行 hard-gate、Goal relation、三次分布與 blinded-order tests**

Run: `python -m unittest packages/router-core/tests/evaluation/test_scoring.py packages/router-core/tests/evaluation/test_comparison.py -v`

Expected: PASS；任何 hard violation 都使 release ineligible；上層強制能力不被誤算為 Router support。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/evaluation/scoring.py packages/router-core/src/workflow_skill_router/evaluation/comparison.py packages/router-core/tests/evaluation
git commit -m "feat(eval): enforce hard gates and paired comparison"
```

### Task 5: Sanitized reporting 與 V1 Tier 0 compatibility

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/evaluation/reporting.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/attestation.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/legacy_v1.py`
- Create: `packages/router-core/src/workflow_skill_router/evaluation/composition.py`
- Create: `packages/router-core/tests/evaluation/test_reporting.py`
- Create: `packages/router-core/tests/evaluation/test_attestation.py`
- Create: `packages/router-core/tests/evaluation/test_legacy_v1.py`
- Modify: `packages/router-core/src/workflow_skill_router/service_models.py`
- Modify: `packages/router-core/src/workflow_skill_router/service.py`
- Modify: `packages/router-core/src/workflow_skill_router/ports.py`
- Modify: `packages/router-core/src/workflow_skill_router/composition.py`
- Create: `packages/router-core/tests/integration/test_evaluation_service.py`
- Create: `packages/router-core/tests/integration/test_evaluation_composition.py`
- Modify: `evaluation/README.md`
- Modify: `evaluation/schema.md`
- Create: `evaluation/v2/report.example.md`

**Interfaces:**
- Consumes: `EvaluationScore`、`EvaluationComparison`、V1 JSONL fixtures、server-validated `EvalExportAuthorization`，以及 injected `ReviewAttestationVerifier.resolve_and_verify(attestation_ref, expected_review_subject_digest, expected_redaction_manifest_digest, expected_publication_policy_digest, now) -> VerifiedReviewReceipt`。Plain attestation JSON/file path 不是 trust source。
- Produces: `build_review_draft(...) -> ExportArtifact`；`calculate_review_subject_digest(artifact: ExportArtifact | PublishedArtifact) -> str`；`calculate_artifact_digest(artifact_without_digest) -> str`；`publish_sanitized(context, authorization, draft, attestation_ref, verifier, now) -> ExportArtifact`；`load_legacy_v1_contract(...) -> ContractSuite` with `tier="T0"` and `evidence_class="contract-only"`；`RouterService.run_model_evaluation`、CLI-only `RouterService.import_model_evaluation`、`RouterService.compare_evaluations`、`RouterService.export_router_artifact`。There is no permissive default verifier。

- [ ] **Step 1: 寫出無 attestation 不可 public 與 V1 禁止升格的失敗測試**

```python
def test_public_export_requires_matching_human_attestation(self):
    draft = build_review_draft(self.comparison, self.output)
    self.assertEqual(draft.status, "review-draft")
    with self.assertRaisesRegex(ExportPolicyError, "attestation_required"):
        publish_sanitized(CONTEXT, self.publish_authorization, draft, None, RejectUnverifiedAttestation(), NOW)

def test_self_declared_reviewer_is_not_treated_as_human_authority(self):
    draft = build_review_draft(self.comparison, self.output)
    with self.assertRaisesRegex(ExportPolicyError, "trusted_human_attestation_required"):
        publish_sanitized(CONTEXT, self.publish_authorization, draft, "self-declared:agent", RejectUnverifiedAttestation(), NOW)

def test_review_subject_digest_excludes_publication_metadata_without_becoming_circular(self):
    draft = build_review_draft(self.comparison, self.output)
    published = publish_sanitized(
        CONTEXT, self.publish_authorization, draft,
        "host-review-receipt-9", self.trusted_verifier, NOW,
    )
    self.assertEqual(published.review_subject_digest, calculate_review_subject_digest(draft))
    self.assertEqual(published.artifact_digest, calculate_artifact_digest(published.without_artifact_digest()))
    changed_metadata = replace(published, published_at="2030-01-01T00:00:00Z")
    self.assertEqual(published.review_subject_digest, calculate_review_subject_digest(changed_metadata))
    self.assertNotEqual(published.artifact_digest, calculate_artifact_digest(changed_metadata.without_artifact_digest()))

def test_mutating_sanitized_payload_invalidates_verified_receipt(self):
    draft = build_review_draft(self.comparison, self.output)
    changed = replace(draft, sanitized_payload={"summary": "被竄改"})
    with self.assertRaisesRegex(ExportPolicyError, "review_subject_digest_mismatch"):
        publish_sanitized(CONTEXT, self.publish_authorization, changed, "host-review-receipt-9", self.trusted_verifier, NOW)

def test_export_authorization_cannot_publish_when_issued_for_draft(self):
    with self.assertRaisesRegex(EvaluationAuthorizationError, "export_action_mismatch"):
        publish_sanitized(CONTEXT, self.draft_authorization, self.draft, "host-review-receipt-9", self.trusted_verifier, NOW)

def test_expired_revoked_or_timeless_review_receipt_cannot_publish(self):
    for receipt in (
        self.review_receipt(expires_at="2026-07-14T00:00:00Z"),
        self.review_receipt(revoked=True),
        self.review_receipt(reviewed_at=None),
    ):
        with self.subTest(receipt=receipt):
            verifier = StubReviewVerifier(receipt)
            with self.assertRaisesRegex(ExportPolicyError, "review_attestation_invalid"):
                publish_sanitized(
                    CONTEXT, self.publish_authorization, self.draft,
                    receipt.receipt_ref, verifier, now=NOW,
                )

def test_human_review_cannot_publish_release_ineligible_source(self):
    draft = replace(self.draft, source_release_decision=ReleaseDecision(False, ("mandatory-outcome-failed",)))
    with self.assertRaisesRegex(ExportPolicyError, "source_not_release_eligible"):
        publish_sanitized(
            CONTEXT, self.publish_authorization, draft,
            "host-review-receipt-9", self.trusted_verifier, NOW,
        )

def test_legacy_eighty_cases_are_tier_zero_contract_only(self):
    suite = load_legacy_v1_contract(Path("evaluation/scenarios.example.jsonl"))
    self.assertEqual(len(suite.cases), 80)
    self.assertEqual((suite.tier, suite.evidence_class), ("T0", "contract-only"))
    self.assertNotIn("real model", suite.claims)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest packages/router-core/tests/evaluation/test_reporting.py packages/router-core/tests/evaluation/test_attestation.py packages/router-core/tests/evaluation/test_legacy_v1.py -v`

Expected: FAIL because reporting/legacy adapters do not exist。

- [ ] **Step 3: 實作 redaction、attestation digest 與 legacy labeling**

```python
def publish_sanitized(context, authorization, draft, attestation_ref, verifier, now):
    validate_export_authorization(context, authorization, draft.source_digest, action="publish")
    if not draft.source_release_decision.eligible:
        raise ExportPolicyError("source_not_release_eligible")
    if not attestation_ref:
        raise ExportPolicyError("attestation_required")
    if draft.redaction_findings:
        raise ExportPolicyError("sanitization_findings_unresolved")
    subject_digest = calculate_review_subject_digest(draft)
    receipt = verifier.resolve_and_verify(
        attestation_ref,
        expected_review_subject_digest=subject_digest,
        expected_redaction_manifest_digest=draft.redaction_manifest_digest,
        expected_publication_policy_digest=authorization.artifact_policy_digest,
        now=now,
    )
    if (
        not receipt.trusted or receipt.actor_type != "human" or not receipt.reviewer_id
        or not receipt.reviewed_at or parse_utc(receipt.reviewed_at) > now
        or parse_utc(receipt.expires_at) <= now or receipt.revoked
        or receipt.review_subject_digest != subject_digest
        or receipt.redaction_manifest_digest != draft.redaction_manifest_digest
        or receipt.publication_policy_digest != authorization.artifact_policy_digest
    ):
        raise ExportPolicyError("review_attestation_invalid")
    artifact = PublishedArtifact.from_draft(
        draft,
        review_subject_digest=subject_digest,
        review_receipt_ref=receipt.receipt_ref,
        review_receipt_digest=receipt.receipt_digest,
        review_authority=receipt.authority_ref,
        reviewer_id=receipt.reviewer_id,
        reviewed_at=receipt.reviewed_at,
        review_policy_digest=receipt.publication_policy_digest,
    )
    return replace(artifact, artifact_digest=calculate_artifact_digest(artifact.without_artifact_digest()))
```

`review_subject_digest` 的 canonical subject 只包含 `schema_id`、`schema_version`、`artifact_kind`、sanitized payload、source run/comparison manifest digest、server-owned source `ReleaseDecision` and redaction manifest digest；明確排除 `status`、`published_at`、`attestation_ref`、verified authority metadata、publication envelope 與 `artifact_digest`。`artifact_digest` 則對「已含 review subject digest／verified receipt reference，但排除 artifact_digest 欄位本身」的完整 final envelope 計算。兩個 digest 各有單一用途，不可互相比較或遞迴包含。Human attestation approves a sanitized eligible artifact；it cannot override a diagnostic/ineligible score。Such sources may produce status-only or review-draft output with no public score claim, never `published`。

`attestation.py` defines the verifier protocol、fail-closed `RejectUnverifiedAttestation` and exact frozen `VerifiedReviewReceipt(receipt_ref, receipt_digest, authority_ref, reviewer_id, actor_type, reviewed_at, expires_at, revoked, revocation_epoch, review_subject_digest, redaction_manifest_digest, publication_policy_digest, trusted)`。A host adapter resolves and verifies an opaque signed host approval receipt against the current server revocation registry；an external reviewer adapter may verify an organization-controlled signature out of process。Core accepts only opaque `attestation_ref`, never a client reviewer DTO or plain file path。It independently checks stable reviewer ID、human actor、review time、expiry/revocation、subject/redaction/policy bindings and stores them in the final publication envelope。`artifact_digest` therefore binds receipt digest/ref、reviewer ID、reviewed_at、authority and publication policy。Username、environment variable、file existence or client boolean cannot prove human review；a receipt issued under an older policy cannot be replayed after policy change。

Extend `service_models.py` with frozen evaluation commands/results。Each command carries RequestContext/idempotency/correlation；mutations decode only typed JSON/stdin。RouterService receives evaluation ports only from the canonical `composition.open(...)` extended below；authorization is server-issued/validated。Import accepts bundle ID + write-only one-time token while bundle owns opaque auth ref。Export accepts opaque attestation ref；the canonical composition factory injects trusted verifier and client cannot choose it。Tests cover single-use import/idempotency/cross-session/manifest mismatch and reject embedded trust/authorization fields。

`evaluation/composition.py` defines the exact frozen aggregate `EvaluationCompositionPorts(authorization_store, run_authorizer, import_authorizer, compare_authorizer, export_authorizer, adapter_registry, worker_broker, isolation_receipt_verifier, cancellation_port, evaluation_store, scoring_key_resolver, release_policy_repository, scorer, review_verifier_registry, manual_trace_reader, collection_receipt_verifier)`。`ReviewVerifierRegistry` is server-owned：it maps opaque receipt authority/scheme only from verified native-host or organization adapter registrations, checks pinned keys/revocation policy, and otherwise delegates to `RejectUnverifiedAttestation`。The request/CLI can submit only an opaque receipt ref and cannot select/register a verifier。Every aggregate field is a concrete typed Protocol implementation；missing/dynamic objects fail construction。Plan 05 modifies the one canonical factory to:

```python
def open(
    database: Path,
    artifact_root: Path,
    runtime_adapter: RuntimeAdapter,
    request_authorizer: RequestAuthorizer,
    instruction_content_resolver: InstructionContentResolver,
    artifact_protector: ArtifactProtector,
    activation_preflight: ActivationPreflightPort,
    evaluation_ports: EvaluationCompositionPorts,
    clock: Clock = SystemClock(),
    id_factory: IdFactory = UuidFactory(),
) -> RouterService: ...
```

There is no second service constructor。The factory wires the same shared SQLite transaction manager/content-addressed artifact store into routing and evaluation, then injects all evaluation ports into four application methods：three public MCP methods plus CLI-only `import_model_evaluation`。`test_evaluation_composition.py` opens one real service with deterministic concrete fakes and proves the ten public methods plus the CLI-only import method are callable, authorizations remain server-owned, worker/cancellation/release/attestation ports are the injected instances, and omitting or substituting any required port fails before serving。It also proves a host-signed receipt resolves only after verified registry registration, while a client-supplied verifier/authority override remains rejected。Plan 04 `open_plugin_service(...)` must build this aggregate from verified bridge/runtime adapters and delegate exactly once to this factory。

This plan freezes the versioned evaluation command/result schemas and direct service integration only；it does not create or modify the CLI because the canonical `cli/` package is created later by Plan 04 after the ten public methods and CLI-only import method exist。Plan 04 must expose these exact schemas as `evaluation run|import|compare|export|publish|export-status --input <command.json>|stdin` with no alternate flags, and must test manual-required→single-use import plus plain-attestation rejection。

Sanitizer 至少掃描 credential patterns、Windows/Unix private paths、hostname、repo path、prompt 與 user content。`legacy_v1.py` 直接讀取 V1 JSONL 或以 subprocess 呼叫未修改的 `scripts/evaluate-routing.py`；只有新的 V2 report/docs 顯示 `Tier 0 Contract — deterministic fixture, not a real-model evaluation`。Legacy script 不得 import `packages/router-core`，其 arguments、stdout/stderr 與 exit codes 必須逐 byte 保持不變。

- [ ] **Step 4: 跑評測全套與既有 CLI regression**

Run: `python -m unittest discover -s packages/router-core/tests/evaluation -v && python -m unittest packages/router-core/tests/integration/test_evaluation_service.py packages/router-core/tests/integration/test_evaluation_composition.py -v`

Expected: PASS。

Run: `python -m unittest tests/test_evaluate_routing.py -v`

Expected: PASS；80 fixtures 繼續通過，legacy stdout/stderr 逐 byte 不變；只有 V2 adapter／report 顯示 Tier 0 Contract 標籤。

- [ ] **Step 5: Commit**

```bash
git add packages/router-core/src/workflow_skill_router/evaluation packages/router-core/src/workflow_skill_router/service_models.py packages/router-core/src/workflow_skill_router/service.py packages/router-core/src/workflow_skill_router/ports.py packages/router-core/src/workflow_skill_router/composition.py packages/router-core/tests/evaluation packages/router-core/tests/integration/test_evaluation_service.py packages/router-core/tests/integration/test_evaluation_composition.py evaluation
git commit -m "feat(eval): publish attested reports and label v1 contracts"
```

## Plan Verification

- [ ] Run: `python -m unittest discover -s packages/router-core/tests/evaluation -v` — Expected: all evaluation tests PASS。
- [ ] Run: `python -m unittest tests/test_evaluate_routing.py -v` — Expected: legacy Contract suite PASS，既有 flags/exit codes 不變。
- [ ] Run: `rg -n "real model|真實模型" evaluation packages/router-core/src/workflow_skill_router/evaluation` — Expected: 只出現在否定 fixture claim 或 Behavior／Outcome 說明，不得用於 V1 fixture 成績宣稱。
- [ ] Run: `python -m unittest packages/router-core/tests/integration/test_evaluation_service.py packages/router-core/tests/integration/test_evaluation_composition.py -v` — Expected: direct service manual-required→single-use import、same-key replay、different-key/cross-session/tamper/authorization widening fail closed，and the canonical factory wires all ten public methods、CLI-only import and every evaluation trust port。CLI transport is intentionally deferred to Plan 04。
- [ ] Run: `python -m unittest packages/router-core/tests/evaluation/test_authorization.py packages/router-core/tests/evaluation/test_artifact_protection.py packages/router-core/tests/evaluation/test_reporting.py -v` — Expected: compare/export scope binding、共用 ArtifactProtector/Store、OS/encryption protection honesty、tombstone/crypto erase、非循環 review/artifact digests 全部 PASS。
