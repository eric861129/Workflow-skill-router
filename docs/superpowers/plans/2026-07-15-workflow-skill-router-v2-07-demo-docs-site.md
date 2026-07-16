# Workflow Skill Router V2 Demo, Documentation, and Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以單一、經清理且可驗證的 V2 demo 資料源，重建互動網站、雙語文件、README、媒體資產與視覺／效能驗證。

**Architecture:** `demo/v2-scenarios/inputs.json` 只保存六種 sanitized request、capability snapshot input、Goal context 與 consent replies，不保存 RequestDecision、route、policy result 或 event trace。Python builder 以 deterministic clock/ID factory 啟動暫存 `RouterService`，由專用 `DemoScenarioExporter` 呼叫真正的 discovery／plan／validate／consent／Goal contracts，輸出預先計算且綁定 core/schema digest 的 branches。Astro/TypeScript 只能切換與 render branches，不得重新判斷 routing 或 consent。Public evaluation artifact 必須由 plan 05 reporting pipeline 產生並經 trusted verifier；沒有 verified human receipt 時只顯示 `review-required|manual-required`，不把 deterministic fixture 包裝成真實模型結果。

**Tech Stack:** Python 3.11+ standard library、Astro 6、Starlight 0.40、TypeScript/Astro、Playwright 1.61、Lighthouse 13、Node 24、`ffmpeg-static` 5.2.0。

## Global Constraints

- Demo 至少包含：small auto、小型指定 SKILL 並拒絕 support、中型指定 SKILL 的 phase consent、中型 auto、Goal graph、real model evaluation。
- V1 80-case fixture 只能標示 `Tier 0 Contract`；real model evaluation preset 只能讀取具 provenance 的 Behavior／Outcome artifact。沒有可用 adapter 時顯示 `manual-required`；已執行但沒有 trusted human receipt 時顯示 `review-required`，兩者都不得顯示分數。
- Canonical scenario/public artifact 不含 secret、hostname、私人 repo/user path、credential、未經同意的 prompt/user content；全部 UTF-8。
- Demo input 不得含 `request_decision`、`route`、`active_selections`、`policy_result` 或 hand-authored event；這些只能由 `RouterService`／`DemoScenarioExporter` 產生。Frontend 不得含 envelope/skill/consent 決策表。
- Root/CI 執行 demo builder 前必須從 `packages/router-core` 安裝 wheel/package；fresh clone 不可依賴開發機既有 `PYTHONPATH`。Local focused test 可暫用明示 `PYTHONPATH`，但 release gate 必須驗 installed entry point。
- `site/src/data/router-demo-v2.generated.json` 與影音為 generated artifacts，CI 使用 `--check` 驗證 drift。
- 英文與繁體中文必須有相同的導航、scenario coverage、consent/Goal/evaluation disclosure 與可操作連結。
- Lighthouse budgets：Performance ≥ 0.90、Accessibility ≥ 0.95、Best Practices ≥ 0.95、SEO ≥ 0.95；CI 不可只保存 report 而忽略 threshold failure。

---

## File Map

- `demo/v2-scenarios/inputs.json`、`schema.json`：六個 canonical sanitized request/capability/Goal/consent inputs，不含 routing outputs。
- `packages/router-core/src/workflow_skill_router/demo_export.py`：用真正 `RouterService` 產生 deterministic precomputed branches 與 trace digests。
- `evaluation/artifacts/public/v2-demo-evaluation.json`、`v2-demo-evaluation.redaction-manifest.json`：由 plan 05 trusted reporting pipeline 產生的公開狀態與遮罩證據；不簽入可被誤認為 portable authority 的 review receipt。
- `scripts/build-v2-demo-data.py`：input validation、core exporter orchestration、sanitization 與 generated data checker。
- `site/src/data/router-demo-v2.generated.json`：Astro 唯一 demo input。
- `site/src/components/AdaptiveRouterDemo.astro`：Single／Phased／Goal／Eval interactive component。
- `site/src/content/docs/**`、`README*.md`、`evaluation/*.md`、`docs/showcase.md`：雙語說明與證據界線。
- `site/scripts/generate-demo-assets.mjs`：從 canonical demo page 產生 poster/WebM/MP4。
- `site/tests/smoke.spec.ts`、`visual.spec.ts`、`__screenshots__/**`：雙語互動、a11y smoke 與 snapshots。
- `.github/workflows/validate.yml`：data/media generation check、site build、雙語 Playwright、Lighthouse budgets。

### Task 1: 建立 canonical sanitized V2 scenarios 與 deterministic generator

**Files:**
- Create: `demo/v2-scenarios/schema.json`
- Create: `demo/v2-scenarios/inputs.json`
- Create: `demo/v2-scenarios/fixture-installer-manifest.json`
- Create: `demo/v2-scenarios/fixture-skills/*/SKILL.md`（small/phase/goal/support 所需的最小 sanitized bodies）
- Create: `packages/router-core/src/workflow_skill_router/demo_export.py`
- Create: `packages/router-core/tests/demo/test_demo_export.py`
- Create: `scripts/build-v2-demo-data.py`
- Create: `tests/test_v2_demo_data.py`
- Create (generated): `site/src/data/router-demo-v2.generated.json`

**Interfaces:**
- Consumes: `demo/v2-scenarios/inputs.json`、plan 03 `composition.open(...)`/`RouterService` typed APIs/event projection、optional status-only `evaluation/artifacts/public/v2-demo-evaluation.json` and redaction manifest；a completed score is available only during a live injected verified-review session and is not inferred from checked-in receipt metadata。
- Produces: `DemoScenarioInputs`；`open_demo_export_service(root, inputs, clock, ids) -> RouterService`；`DemoScenarioExporter.export(inputs: DemoScenarioInputs) -> DemoScenarioArtifact`；`build_demo_data(repo_root: Path) -> dict[str, object]`；CLI `python scripts/build-v2-demo-data.py [--check]`；generated schema `workflow-skill-router/demo-data@2.0.0-alpha.1` with `router_core_digest`、`schema_revision`、`runtime_input_digest`、`branches[]` and `trace_digest`。

- [ ] **Step 1: 寫六 presets、隱私與 deterministic output 失敗測試**

```python
EXPECTED = {
    "small-auto", "small-explicit-reject-support",
    "medium-explicit-phase-consent", "medium-auto",
    "goal-work-graph", "real-model-evaluation",
}

def test_demo_has_required_sanitized_presets(self):
    data = build_demo_data(ROOT)
    self.assertEqual({item["id"] for item in data["presets"]}, EXPECTED)
    encoded = json.dumps(data, ensure_ascii=False)
    self.assertNotRegex(encoded, r"[A-Za-z]:\\Users\\|/Users/|/home/|sk-[A-Za-z0-9]")

def test_input_source_contains_no_hand_authored_policy_outputs(self):
    source = json.loads(Path("demo/v2-scenarios/inputs.json").read_text("utf-8"))
    forbidden = {"request_decision", "route", "active_selections", "policy_result", "events"}
    for preset in source["presets"]:
        self.assertTrue(forbidden.isdisjoint(preset))

def test_rejected_support_keeps_audit_but_has_no_active_support_or_activation(self):
    preset = preset_by_id(build_demo_data(ROOT), "small-explicit-reject-support")
    rejected = branch_by_id(preset, "support-rejected")
    self.assertEqual(rejected["route"]["support_selections"], [])
    self.assertTrue(any(e["event_type"] == "SUPPORT_SKILL_PROPOSED" for e in rejected["events"]))
    self.assertTrue(any(e["event_type"] == "SUPPORT_SKILL_REJECTED" for e in rejected["events"]))
    self.assertFalse(any(
        e["event_type"] == "CAPABILITY_ACTIVATION_OBSERVED" and e["payload"]["capability_id"] == "skill:qa-support"
        for e in rejected["events"]
    ))
    self.assertEqual(rejected["explicit_skill_coverage"]["status"], "satisfied")

def test_public_real_eval_is_honest_without_portable_attestation(self):
    preset = preset_by_id(build_demo_data(ROOT), "real-model-evaluation")
    self.assertIn(preset["status"], {"manual-required", "review-required"})
    self.assertNotIn("score", preset)
    self.assertNotIn("reviewer_id", preset)

def test_forged_checked_in_receipt_cannot_upgrade_public_evaluation(self):
    with forged_public_fixture(ROOT, recompute_local_digests=True) as fixture_root:
        preset = preset_by_id(build_demo_data(fixture_root), "real-model-evaluation")
        self.assertEqual("review-required", preset["status"])
        self.assertNotIn("score", preset)

def test_rejected_support_never_reaches_instruction_or_activation_preflight(self):
    exporter = exporter_with_spy_resolver_and_preflight()
    exporter.export(INPUT_WITH_REJECTED_SUPPORT)
    self.assertNotIn("skill:qa-support", exporter.spy_resolver.opened_capability_ids)
    self.assertNotIn("skill:qa-support", exporter.spy_preflight.bound_capability_ids)
```

- [ ] **Step 2: 驗證測試先紅燈**

Run: `python -m unittest tests/test_v2_demo_data.py -v`

Expected: FAIL with missing demo builder/source。

- [ ] **Step 3: 實作 scenario schema 與 generator**

```python
def build_demo_data(repo_root: Path) -> dict[str, object]:
    scenario_inputs = load_and_validate(repo_root / "demo/v2-scenarios/inputs.json")
    evaluation = load_public_evaluation_or_manual_required(repo_root)
    with TemporaryDirectory() as directory:
        service = open_demo_export_service(
            root=Path(directory),
            inputs=scenario_inputs,
            clock=FixedClock("2026-07-15T00:00:00Z"),
            ids=DeterministicIdFactory("workflow-router-v2-demo"),
        )
        exporter = DemoScenarioExporter(service)
        routed = [exporter.export(DemoScenarioInputs.from_dict(item)) for item in scenario_inputs["presets"]]
    output = {
        "schema_id": "workflow-skill-router/demo-data",
        "schema_version": "2.0.0-alpha.1",
        "artifact_kind": "interactive-demo",
        "router_core_digest": exporter.router_core_digest,
        "schema_revision": exporter.schema_revision,
        "presets": [attach_evaluation(item.to_dict(), evaluation) for item in routed],
    }
    assert_public_safe(output)
    return output
```

`open_demo_export_service()` 是 `demo_export.py` 中明確定義的 generator-only composition helper；它呼叫唯一的 final `composition.open(database, artifact_root, runtime_adapter, request_authorizer, instruction_content_resolver, artifact_protector, activation_preflight, evaluation_ports, clock, id_factory)`。It injects verified demo runtime/request adapters、fixture-only instruction/runtime-contract resolvers、temporary-root protector、single-use activation preflight、Plan 05 complete demo `EvaluationCompositionPorts` whose review registry is reject-by-default、and deterministic clock/IDs。Adapters 只接受 `artifact_kind=demo-scenario-input` 與通過 schema/sanitization 的資料；Plugin/MCP/一般 CLI 不得註冊。Tests reject production schema、arbitrary paths、client trust and unsanitized input；helper 不含 routing/consent policy。

每個 input preset 只可包含 localized title/request、request constraints、frontmatter-only capability metadata、Goal snapshot input 與依 trigger 排序的 user consent replies。Minimal checked-in fixture SKILL bodies 位於獨立 allowlisted root，內容只有 synthetic public text；trusted fixture installer manifest pins every body SHA-256，resolver rejects any path/symlink/unlisted file。`DemoScenarioExporter` 對每個 reply 建立隔離 child workflow and follows the real order：sync → plan/preview route（no lease/body read）→ emit support proposal → apply consent grant/rejection → final validate route → kind-specific single-use preflight only for approved selections → activation/evidence → projection export。Approve/reject branches隔離，rejected support never reaches instruction resolver/preflight，and Goal Work Item reclassification preserves anchors。Exporter only normalizes/sanitizes/maps presentation。`--check` reruns core and byte-compares all digests/branches。

`load_public_evaluation_or_manual_required()` never treats a checked-in receipt JSON、`trusted` boolean or recomputed digest as authority。The deterministic fresh-clone generator has no live review verifier, so it always converts checked-in evaluation material to `review-required`/`manual-required` and strips scores。Only an injected server-owned Plan 05 `ReviewVerifierRegistry` may expose a completed score during a live trusted run；that live result stays under ignored `.artifacts/` unless a future portable offline signature format and pinned public authority are explicitly versioned。The V2 alpha public repo does not claim such portable trust。

- [ ] **Step 4: 生成並檢查 demo data**

Run: `$env:PYTHONPATH='packages/router-core/src'; python scripts/build-v2-demo-data.py && python scripts/build-v2-demo-data.py --check && python -m unittest packages/router-core/tests/demo/test_demo_export.py tests/test_v2_demo_data.py -v`

Expected: PASS，generated JSON 只由 canonical sources 產生。

- [ ] **Step 5: Commit**

```bash
git add demo packages/router-core/src/workflow_skill_router/demo_export.py packages/router-core/tests/demo/test_demo_export.py scripts/build-v2-demo-data.py tests/test_v2_demo_data.py site/src/data/router-demo-v2.generated.json
git commit -m "feat(demo): generate canonical v2 router scenarios"
```

### Task 2: 產生具 provenance 的 public evaluation artifact

**Files:**
- Create (generated): `evaluation/artifacts/public/v2-demo-evaluation.json`
- Create (generated): `evaluation/artifacts/public/v2-demo-evaluation.redaction-manifest.json`
- Create: `evaluation/v2/requests/demo-behavior-run.json`
- Create: `evaluation/v2/requests/demo-review-draft-export.json`
- Create: `evaluation/v2/requests/demo-review-required-export.json`
- Modify: `tests/test_v2_demo_data.py`

**Interfaces:**
- Consumes: plan 05 `RouterService.run_model_evaluation`、`build_review_draft`、`publish_sanitized`、`calculate_review_subject_digest`、`calculate_artifact_digest` 與 injected trusted `ReviewAttestationVerifier`；sealed Behavior suite `evaluation/v2/suites/manifest.json`。
- Produces: local live completed artifact under ignored `.artifacts/` only when the server-owned verifier resolves a current trusted receipt；checked-in public artifact is status=`review-required|manual-required` without score and includes only safe provenance/limitations。Agent/model 不得建立 reviewer identity、human attestation 或把 plain file 當 trust source。

- [ ] **Step 1: 寫禁止 handcrafted score 的失敗測試**

```python
def test_checked_in_public_eval_is_honest_without_portable_review_authority(self):
    artifact = load_public_eval()
    self.assertIn(artifact["status"], {"review-required", "manual-required"})
    self.assertNotIn("score", artifact)
    self.assertNotIn("trusted", artifact)
    self.assertNotIn("reviewer_id", artifact)

def test_plain_or_forged_review_receipt_file_never_upgrades_checked_in_artifact(self):
    artifact = rebuild_public_eval_with_forged_receipt_and_valid_local_digests()
    self.assertEqual("review-required", artifact["status"])
    self.assertNotIn("score", artifact)
```

- [ ] **Step 2: 以共用 typed CLI contract 執行 real evaluation 或 honest manual-required**

`evaluation/v2/requests/demo-behavior-run.json` 使用 plan 05 `RunModelEvaluation` schema，固定 `RequestContext(session_id="v2-demo-docs", actor="agent", runtime_policy_snapshot_id="demo-policy-v1")`、suite ref、mode=`behavior`、adapter kind=`auto`、repeats=`3`、idempotency key=`v2-demo-behavior-run-1` 與 output root=`.artifacts/evaluation/v2-demo`。它不含 authorization、allowed adapters、trusted actor 或 scoring path；authorization 由 service 依 context/policy 簽發。

Run: `$env:PYTHONPATH='packages/router-core/src'; python -m workflow_skill_router evaluation run --input evaluation/v2/requests/demo-behavior-run.json`

Expected with Host/External adapter: status=`completed` and raw run manifest；Expected without adapter: status=`manual-required` and sealed bundle, no score。

- [ ] **Step 3: 由 reporting pipeline 產生 local review draft，不讓 agent 冒充 reviewer**

`demo-review-draft-export.json` 以 `source_run_ref={session_id:"v2-demo-docs", idempotency_key:"v2-demo-behavior-run-1"}` 解析 server-owned run，action=`draft`，output=`.artifacts/evaluation/v2-demo/review-draft.json`；不允許 client 傳入 export authorization 或 reviewer trust。

Run: `$env:PYTHONPATH='packages/router-core/src'; python -m workflow_skill_router evaluation export --input evaluation/v2/requests/demo-review-draft-export.json`

Expected for completed run: secret/path scan PASS，產生 local `review-draft.json` 與 redaction manifest，status=`review-required`；不得產生 attestation 或 public score。Expected for manual-required: 只產生未執行 disclosure，不含 metrics。

- [ ] **Step 4: 只接受 trusted verifier 的 opaque human receipt，否則發布無分數狀態**

Human review 針對 plan 05 canonical `review_subject_digest` 與 redaction manifest digest 進行。Host approval adapter 或 organization-controlled external verifier 驗證後，回傳 opaque `attestation_ref` 並以受信任 integration 建立 `.artifacts/evaluation/v2-demo/publish-command.json`。該 command 只含 `RequestContext`、source review draft ref、action=`publish`、opaque `attestation_ref`、idempotency/output fields；不得含 reviewer DTO、`trusted=true` 或 attestation file path。檔案存在本身不授予信任；core 仍須由 injected verifier resolve receipt、驗 human actor 與兩個 digest。

Run when trusted integration produced the command: `$env:PYTHONPATH='packages/router-core/src'; python -m workflow_skill_router evaluation publish --input .artifacts/evaluation/v2-demo/publish-command.json`

Expected: verifier resolution、human authority、review subject/redaction/policy digest、expiry/revocation 全部相符才輸出 completed artifact與分數到 ignored local `.artifacts/`；integrity/policy mismatch exit 65。The checked-in public output is always produced by `demo-review-required-export.json` with action=`status-only` and status=`review-required|manual-required`。Run `$env:PYTHONPATH='packages/router-core/src'; python -m workflow_skill_router evaluation export-status --input evaluation/v2/requests/demo-review-required-export.json`。Expected: only provenance、limitations and review/manual status, no score or receipt trust metadata。Agent/model不得自行建立 opaque receipt or treat ordinary JSON as human review。

- [ ] **Step 5: 重建 site data 並驗證 claim**

Run: `python scripts/build-v2-demo-data.py && python -m unittest tests/test_v2_demo_data.py -v`

Expected: PASS；completed preset 顯示實際 manifest/model/adapter/repeats；review-required/manual-required preset 只顯示 provenance、執行方式與限制，不顯示 score。

- [ ] **Step 6: Commit**

```bash
git add evaluation/artifacts/public site/src/data/router-demo-v2.generated.json tests/test_v2_demo_data.py
git commit -m "docs(eval): publish honest v2 demo evaluation status"
```

### Task 3: 建立 AdaptiveRouterDemo 與六種互動流程

**Files:**
- Create: `site/src/components/AdaptiveRouterDemo.astro`
- Create: `site/src/styles/adaptive-router-demo.css`
- Create: `site/src/scripts/adaptive-router-demo.ts`
- Modify: `site/src/components/HomeLanding.astro`
- Modify: `site/src/content/docs/index.mdx`
- Modify: `site/src/content/docs/zh-tw/index.mdx`
- Modify: `site/tests/smoke.spec.ts`

**Interfaces:**
- Consumes: generated `router-demo-v2.generated.json`；props `locale: "en" | "zh-TW"`、`initialPreset?: string`。
- Produces: semantic tabs/buttons、precomputed request decision/route/audit branch、Phase/Goal graph、evaluation disclosure；stable test IDs `demo-preset-*`, `demo-consent-approve`, `demo-consent-reject`, `demo-status`, `demo-audit-proposal`, `demo-active-support`, `demo-activation-event`, `demo-explicit-coverage`。TypeScript 只能選取 branch ID 與 render fields，不得計算 route、skill disposition、consent validity 或 activation。

- [ ] **Step 1: 寫雙語互動與拒絕後不啟用 support 的失敗測試**

```ts
test('explicit skill rejection keeps only the requested skill', async ({ page }) => {
  await page.goto('/zh-tw/');
  await page.getByTestId('demo-preset-small-explicit-reject-support').click();
  await page.getByTestId('demo-consent-reject').click();
  await expect(page.getByTestId('demo-status')).toContainText('僅使用指定 SKILL');
  await expect(page.getByTestId('demo-audit-proposal')).toContainText('router-recommended');
  await expect(page.getByTestId('demo-active-support')).toHaveCount(0);
  await expect(page.getByTestId('demo-activation-event').filter({ hasText: 'skill:qa-support' })).toHaveCount(0);
  await expect(page.getByTestId('demo-explicit-coverage')).toContainText('satisfied');
});

test('goal graph routes every work item independently', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('demo-preset-goal-work-graph').click();
  await expect(page.getByTestId('goal-work-item')).toHaveCount(3);
  await expect(page.getByTestId('work-item-envelope')).toHaveText(['single', 'phased', 'single']);
});
```

- [ ] **Step 2: 驗證 component 尚不存在**

Run: `cd site && npm run build && npm run test:site:smoke`

Expected: FAIL because demo test IDs are absent。

- [ ] **Step 3: 實作 data-driven Astro component**

```astro
---
import demo from '../data/router-demo-v2.generated.json';
import '../styles/adaptive-router-demo.css';
interface Props { locale: 'en' | 'zh-TW'; initialPreset?: string }
const { locale, initialPreset = 'small-auto' } = Astro.props;
---
<section class="adaptive-router-demo" data-router-demo data-locale={locale} data-initial={initialPreset}>
  <div role="tablist" aria-label={locale === 'zh-TW' ? '路由情境' : 'Routing scenarios'}>
    {demo.presets.map((preset) => <button role="tab" data-testid={`demo-preset-${preset.id}`} data-preset={preset.id}>{preset.title[locale]}</button>)}
  </div>
  <div aria-live="polite" data-testid="demo-status"></div>
  <script type="application/json" data-demo-payload set:html={JSON.stringify(demo)} />
</section>
<script>import '../scripts/adaptive-router-demo';</script>
```

新增 `site/src/scripts/adaptive-router-demo.ts` 實作 keyboard tabs 與 precomputed branch selector：approve/reject click 只能以 `branch_id` 從 generated JSON 取回完整 projection，不得新增／移除 capability、推導 envelope、驗 consent 或合成 event。Phase/work graph、active selections、audit proposal/rejection、activation events 與 explicit coverage 全部直接 render core exporter outputs；所有可見文字來自 localized canonical data。加入 static source test，禁止 frontend 出現 routing threshold、skill allowlist、consent scope inheritance 或 event-construction constants。Real eval panel 必須顯示 evidence class/status/limitations。

- [ ] **Step 4: build 與雙語 smoke tests**

Run: `cd site && npm run build && npm run test:site:smoke`

Expected: PASS；六 presets 在英文與繁中皆可操作，keyboard focus/ARIA 狀態正確。

- [ ] **Step 5: Commit**

```bash
git add site/src/components site/src/styles site/src/scripts site/src/content/docs/index.mdx site/src/content/docs/zh-tw/index.mdx site/tests/smoke.spec.ts
git commit -m "feat(site): add adaptive v2 router demo"
```

### Task 4: 重寫 README、evaluation docs、Starlight 雙語與 Showcase

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `README.zh-TW.md`
- Modify: `evaluation/README.md`
- Modify: `evaluation/schema.md`
- Modify: `docs/evaluation-guide.md`
- Modify: `docs/showcase.md`
- Create: `docs/v2-architecture.md`
- Create: `docs/v2-architecture.zh-TW.md`
- Create: `docs/v1-to-v2-upgrade.md`
- Create: `docs/v1-to-v2-upgrade.zh-TW.md`
- Create: `site/src/content/docs/guides/v2-routing.md`
- Create: `site/src/content/docs/zh-tw/guides/v2-routing.md`
- Create: `site/src/content/docs/reference/model-evaluation.md`
- Create: `site/src/content/docs/zh-tw/reference/model-evaluation.md`
- Modify: `site/src/content/docs/showcase.md`
- Modify: `site/src/content/docs/zh-tw/showcase.md`
- Modify: `site/astro.config.mjs`
- Create: `tests/test_v2_documentation.py`

**Interfaces:**
- Consumes: approved V2 spec、actual CLI/tool names、version/channel manifests、canonical demo/eval artifact。
- Produces: consistent English/Traditional Chinese navigation and copy；README quickstart 分開 Skill-only 與 Plugin/MCP；upgrade/rollback/channel matrix；evaluation evidence labels。

- [ ] **Step 1: 加入文件 coverage test**

```python
def test_v2_docs_have_required_claim_boundaries(self):
    for path in REQUIRED_V2_DOCS:
        text = Path(path).read_text("utf-8")
        self.assertIn("Tier 0 Contract", text)
        self.assertRegex(text, r"manual-required|manual required")
        self.assertRegex(text, r"skill-only-fallback|hybrid-full")
```

Create: `tests/test_v2_documentation.py`，另比對三份 README 的 required section IDs 與雙語 Starlight route pairs。

- [ ] **Step 2: 驗證文件 coverage 先紅燈**

Run: `python -m unittest tests/test_v2_documentation.py -v`

Expected: FAIL with missing V2 sections/pages。

- [ ] **Step 3: 以實際 contract 重寫文件**

每份 README 依序包含：價值主張、Single/Phased/Managed Goal、explicit SKILL consent、Skill-only quickstart、Plugin/MCP quickstart、real evaluation evidence boundary、version channels、demo、validation。README.md 仍為主要英文入口但清楚連到繁中；README.en.md 不得保留互相衝突的舊定位。Showcase 引用 canonical preset IDs、`review_subject_digest`、final `artifact_digest` 與 verified receipt reference，不複製手寫分數，也不把 plain attestation file 當信任來源。

- [ ] **Step 4: 驗證雙語、links 與 site build**

Run: `python -m unittest tests/test_v2_documentation.py -v && python scripts/check-markdown-links.py . && cd site && npm run build`

Expected: PASS；英文/繁中 route 都產生，沒有 broken local link。

- [ ] **Step 5: Commit**

```bash
git add README.md README.en.md README.zh-TW.md evaluation docs site/src/content/docs site/astro.config.mjs tests/test_v2_documentation.py
git commit -m "docs: publish v2 architecture and bilingual guidance"
```

### Task 5: 修復 MP4 regeneration 並重建 assets/snapshots

**Files:**
- Modify: `site/package.json`
- Modify: `site/package-lock.json`
- Modify: `site/scripts/generate-demo-assets.mjs`
- Modify (generated): `site/public/assets/workflow-skill-router-demo-poster.png`
- Modify (generated): `site/public/assets/workflow-skill-router-demo.webm`
- Modify (generated): `site/public/assets/workflow-skill-router-demo.mp4`
- Modify (generated): `docs/assets/workflow-skill-router-demo-poster.png`
- Modify (generated): `docs/assets/workflow-skill-router-demo.webm`
- Modify (generated): `docs/assets/workflow-skill-router-demo.mp4`
- Create (generated): `site/public/assets/workflow-skill-router-demo-manifest.json`
- Create (generated): `docs/assets/workflow-skill-router-demo-manifest.json`
- Create: `site/tests/demo-assets.spec.ts`
- Modify: `site/tests/visual.spec.ts`
- Modify (generated): `site/tests/__screenshots__/*.png`

**Interfaces:**
- Consumes: built V2 demo page、`ffmpeg-static` executable。
- Produces: `npm run assets:demo` regenerates all six media files；`--check` validates content digest manifest, dimensions, duration and codecs rather than existence/size only。

- [ ] **Step 1: 寫 MP4 stale-source 失敗測試**

在 `site/scripts/generate-demo-assets.mjs` export `probeAssets()`；Create `site/tests/demo-assets.spec.ts`：

```ts
test('webm and mp4 are regenerated from the same demo revision', async () => {
  const probe = await probeAssets();
  expect(probe.webm.demoRevision).toBe(probe.mp4.demoRevision);
  expect(probe.mp4.codec).toMatch(/h264|avc1/);
  expect(Math.abs(probe.webm.duration - probe.mp4.duration)).toBeLessThan(0.25);
});
```

- [ ] **Step 2: 驗證現有 generator 沒有寫 MP4**

Run: `cd site && npm run assets:demo && npx playwright test tests/demo-assets.spec.ts`

Expected: FAIL because MP4 remains stale or lacks matching demo revision metadata。

- [ ] **Step 3: 用 bundled ffmpeg 從本次 WebM 轉碼 MP4**

```javascript
await execFile(ffmpegPath, [
  '-y', '-i', outputs.siteWebm,
  '-metadata', `comment=demo-revision:${demoRevision}`,
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
  outputs.siteMp4,
]);
await copyFile(outputs.siteMp4, outputs.docsMp4);
```

WebM 同樣寫入可 probe 的 revision metadata；generator 最後寫 `site/public/assets/workflow-skill-router-demo-manifest.json` 與 docs copy，保存 source data SHA-256、每個 output SHA-256/duration/codec/dimensions。`--check` 重新計算並驗證 manifest。

- [ ] **Step 4: 重建 media 與雙語 visual snapshots**

Run: `cd site && npm ci && npm run build && npm run assets:demo && npm run assets:demo:check && npm run test:site:update-snapshots && npm run test:site:visual`

Expected: PASS；visual suite 覆蓋英文/繁中 desktop/mobile、六 presets 至少各一個代表狀態、reduced motion。

- [ ] **Step 5: Commit**

```bash
git add site/package.json site/package-lock.json site/scripts site/public/assets docs/assets site/tests
git commit -m "feat(demo): regenerate v2 media and visual baselines"
```

### Task 6: CI generation、雙語 Playwright 與 Lighthouse budgets

**Files:**
- Modify: `.github/workflows/validate.yml`
- Create: `scripts/verify-installed-v2-demo.py`
- Modify: `site/scripts/lighthouse-audit.mjs`
- Modify: `site/tests/smoke.spec.ts`
- Modify: `site/tests/visual.spec.ts`
- Create: `site/tests/lighthouse-budget.spec.ts`

**Interfaces:**
- Consumes: demo `--check`、media `--check`、Astro build、Playwright projects、Lighthouse routes `/`, `/zh-tw/`, `/showcase/`, `/zh-tw/showcase/`。
- Produces: cross-platform fresh-wheel install verifier plus CI failures on generated drift、repo-import fallback、missing locale behavior、snapshot drift or budget regression；Lighthouse summary retains scores but reports are CI artifacts only。

- [ ] **Step 1: 寫 Lighthouse threshold test**

```javascript
export const budgets = {
  performance: 0.90,
  accessibility: 0.95,
  'best-practices': 0.95,
  seo: 0.95,
};

export function assertBudgets(result) {
  const failures = Object.entries(budgets).filter(([key, minimum]) => result.categories[key].score < minimum);
  if (failures.length) throw new Error(`Lighthouse budget failed: ${JSON.stringify(failures)}`);
}
```

Create: `site/tests/lighthouse-budget.spec.ts`，以 synthetic category result 驗證低於 threshold 必須 throw。

- [ ] **Step 2: 驗證現有 CI 未執行完整 gates**

Run: `cd site && npx playwright test tests/lighthouse-budget.spec.ts`

Expected: FAIL until budget exports/assertion exist。

- [ ] **Step 3: 加入完整 validation steps**

```yaml
- name: Verify built wheel in a fresh isolated environment
  run: python scripts/verify-installed-v2-demo.py --check
- name: Build and validate bilingual demo site
  working-directory: site
  run: |
    npm ci
    npm run assets:demo:check
    npm run build
    npm run test:site:smoke
    npm run test:site:visual
    npm run audit:lighthouse
```

Playwright browser install 必須先完成；Lighthouse server lifecycle 使用現有 script 管理且每個 locale route 套用相同 budget。

`verify-installed-v2-demo.py` creates one `TemporaryDirectory`, creates a new venv, uses the venv Python to build a wheel into a separate temp wheel directory (`pip wheel --no-deps`), installs that exact wheel, removes `PYTHONPATH`/`PYTHONHOME` from the child environment, changes cwd outside the repository, and runs `-I -m workflow_skill_router.demo_export --repo-root <absolute-repo> --check` plus the installed console/CLI smoke commands。It verifies the imported module path is inside the venv and that packaged JSON/SQL resources load；an existing global/site package or repo source cannot satisfy the gate。Cleanup is owned by `TemporaryDirectory`; the project code never performs recursive deletion。

- [ ] **Step 4: 跑本機最終 site gate**

Run: `python scripts/verify-installed-v2-demo.py --check && python scripts/check-markdown-links.py . && cd site && npm ci && npm run assets:demo:check && npm run assets:social:check && npm run build && npm run test:site:smoke && npm run test:site:visual && npm run audit:lighthouse`

Expected: 全部 PASS；summary 中四項 score 均達 budget，英文與繁中皆有 results。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/validate.yml scripts/verify-installed-v2-demo.py site/scripts/lighthouse-audit.mjs site/tests
git commit -m "ci(site): gate bilingual demo quality and performance"
```

## Plan Verification

- [ ] `python scripts/verify-installed-v2-demo.py --check` — Expected: a wheel installed into a brand-new temp venv executes outside repo with isolated mode/no `PYTHONPATH`；builder invokes the installed real RouterService and generated branches/core/schema/input/trace digests match canonical inputs。Existing site-packages or repo source cannot mask missing package data/entrypoints。
- [ ] `python -m unittest tests/test_v2_demo_data.py tests/test_v2_documentation.py -v` — Expected: 六 presets、claim boundary、privacy、雙語 coverage 全部 PASS。
- [ ] `cd site && npm run assets:demo:check` — Expected: poster/WebM/MP4 都綁定相同 demo revision；MP4 為本次生成而非舊檔。
- [ ] `cd site && npm run build && npm run test:site:smoke && npm run test:site:visual` — Expected: 英文/繁中 desktop/mobile 互動與 snapshots PASS。
- [ ] `cd site && npm run audit:lighthouse` — Expected: 所有指定 routes 達到 0.90/0.95/0.95/0.95 budgets。
- [ ] `rg -n "80|fixture|real model|真實模型" README*.md evaluation docs site/src/content` — Expected: 80 fixtures 僅稱 Tier 0 Contract；真實模型 claim 只連到具 provenance、non-circular review subject/artifact digests 與 trusted receipt 的 Behavior/Outcome artifact，或誠實標示 manual-required/review-required。
