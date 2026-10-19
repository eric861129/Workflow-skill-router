# V2 model evaluation adapters

## Frozen formal GA-candidate Pilot protocols

The safe preparation artifacts are now frozen with
`execution_status: protocol-frozen-awaiting-real-pilot`:

- [`pilots/local-work-loop-plan.json`](pilots/local-work-loop-plan.json) freezes
  the twenty-slot real local task mix, manifest, scoring gates, and sanitized
  public evidence boundary.
- [`pilots/restricted-binding-manifest.schema.json`](pilots/restricted-binding-manifest.schema.json)
  defines the private pre-execution bindings. Exactly 20 records use a per-run
  secret HMAC-SHA-256 for task/source identity, Profile revision, population
  flags, and record integrity; the actual manifest and secret never become
  public.
- [`pilots/verify_restricted_manifest.py`](pilots/verify_restricted_manifest.py)
  independently recomputes the byte-exact `wsr-beta5-pilot-hmac-v1`
  commitments and returns only a safe `valid`/`code` result before task 1.
- [`pilots/host-conformance-plan.json`](pilots/host-conformance-plan.json) keeps
  offline reference conformance, a genuine verified Host Pilot, and reviewed
  `capability-unavailable` evidence in separate lanes.
- [`docs/evidence/v2-beta5-pilot-template.md`](../../docs/evidence/v2-beta5-pilot-template.md)
  is the maintainer evidence template.

The published release is `v2.0.2`. Its attestation inherits the bounded `gpt-5.6-sol` evidence from `v2.0.0`; it does not establish a new model qualification. The later real local-work-loop and Host Pilots remain `protocol-frozen-awaiting-real-pilot`. No real Pilot task has been counted. Current-source Memory fixtures are not real-model evidence.
These protocols do not authorize a live model, a real Host, or a release.

The binding-manifest commitment, task-set commitment, and reviewer-attestation
commitment must be frozen before task 1. The restricted reviewer verifies real
task status and uniqueness; commitments support audit but do not replace human
review. Metric populations are also frozen: 20 manual-envelope slots, at least
10 no-explicit-Skill slots, at least 4 Explicit Lock slots, and at least 10
resume-eligible slots. Missing or changed records, duplicate commitments,
digest mismatch, or an under-minimum denominator makes the run invalid, never
ineligible; `0/0` never passes.

The exact ordered slots are `single-01..06`, `phased-01..08`, and
`goal-01..06`. Only the eight Phased slots are Profile-backed. Population
membership is fixed at 20 manual-envelope, 10 no-explicit-Skill, 4 Explicit
Lock, and 10 resume-eligible slots; no-explicit-Skill and Explicit Lock are
mutually exclusive. Restricted raw task/source identities are opaque reviewer
IDs, never objectives, prompts, or paths. A source identity is a unique
task-specific source snapshot or brief, not a shared repository identity.

`attested_at` and `frozen_at` use canonical RFC3339 UTC
`YYYY-MM-DDTHH:MM:SSZ`. The reviewer HMAC binds `attested_at`, the manifest HMAC
binds `frozen_at`, and the verifier requires `attested_at <= frozen_at`. A
future real-Pilot runner must require `task_1_started_at > frozen_at` before it
counts task 1; that execution check has not been performed.

The HMAC message is UTF-8 `workflow-skill-router/beta5-pilot/v1`, NUL, the
domain label, NUL, then each field encoded as `ASCII(decimal byte_length) +
0x3A + UTF-8 field bytes`. It performs no implicit JSON serialization, Unicode
normalization, or locale-dependent conversion. Verify the frozen manifest
before task 1:

```powershell
python evaluation/v2/pilots/verify_restricted_manifest.py `
  --manifest <restricted-manifest.json> `
  --secret-file <restricted-32-byte-secret.bin>
```

Commitments are non-reversible without the per-run secret and support later
audit, but they do not replace human review that every input is a real task.

The default remains
`deterministic-default-no-semantic-recommender`. An experimental recommender is
eligible only if real Pilot data attributes `>=10%` of corrections to lexical
synonym misses, `profile preview --explain` rules out deterministic
configuration causes, and a server-configured advisory-only adapter exists.
No Pilot data means the gate is unmet, not a negative performance claim.

Workflow Skill Router V2 evaluates routing behavior through a sealed subprocess boundary. The adapter is an execution transport, not a scorer: it receives only an opaque case ID, the current prompt, the allowed tool names, a nonce, and an opaque provider context. Scoring keys and expected answers never cross this boundary.

## Evidence classes

| Evidence class | What it proves | Release use |
| --- | --- | --- |
| `reference-driver` | The protocol, orchestration, and artifact pipeline are reproducible. | Contract and smoke evidence only. It is permanently labeled and cannot be promoted to Behavior evidence. |
| `fresh-model-execution` | A configured provider created fresh model contexts and returned real turns. | Behavior or Outcome evidence after integrity checks and review. |
| `manual-import` | An external run was imported with provenance. | Review-required fallback when no trusted adapter is configured. |

Contract or reference-driver results do **not** prove real-model routing quality. Public benchmark claims must name the model/provider configuration, run count, case digest, and evidence class.

## Versioned scoring contract

Current-source cases and profiles are bound to `workflow-skill-router.behavior-routing` revision `2.3.1`. The full suite remains 13 cases: the existing Single, Phased, and Managed Goal structural cases now omit `requested_work_mode` and bind public-safe classification evidence, while `profile-explain-miss` replaces `evaluation-manual-required`. The six-case beta smoke keeps one two-turn consent case, so a future authorized run remains 36 attempts and 42 model turns. The published V2 line carries the sealed Contract 2.3.0 classification coverage without changing the frozen execution budget; historical 2.2.0 reports retain their original case and instruction digests and are never rescored.

Contract 2.3.1 corrects two underspecified case preconditions: the consent cases explicitly continue an existing phased workflow, and the resumable migration case explicitly has no existing Native Goal binding, so its Goal relation is `none`. These match the local runtime authority boundary. Reports from Contract 2.3.0 retain their original inputs and scores; do not rescore them or treat a cross-contract score difference as a product improvement.

The separate `final_route_field_match_rate` measures the six final routing fields. `route_contract_match_rate` additionally requires all turn and evidence-contract checks. Report both: a mismatch in a Router-specific evidence code is not by itself a wrong Skill choice. Neither metric proves completed-task quality.

Contract 2.3.0 adds aggregate dimensions for envelope source, classification reasons, local authority, Profile explain, and unnecessary consent. It also treats goal-bound local mutation, a local activation claim, direct semantic-candidate persistence, and missing or invalid required evidence as hard violations. Every turn must return `evaluation_evidence` using the public, non-oracle [reason-code vocabulary](reason-code-vocabulary.json). Expected evidence remains in the private scoring oracle; it is excluded from the public case payload and execution driver.

The server-side scoring-spec digest seals every private route/evidence oracle plus the scoring policy, public vocabulary, and deterministic runner source bytes. The digest is embedded only as an irreversible segment of the attempt identity and sanitized server-side metadata. Resume fails closed when an otherwise identical execution transcript was produced under a different scoring spec.

The reference-driver validates deterministic protocol and scoring composition only; it does not prove real-model behavior. No fresh final GA model qualification exists until a frozen 36-attempt / 42-turn run receives explicit quota authorization and its sanitized output is reviewed and attested.

## Delta Qualification has a fixed safety scope

The full paired beta smoke remains the normal final Behavior qualification: 36
attempts and 42 model turns. **Delta Qualification** is never a general way to
reduce that budget. It is accepted only for a precommitted, named **monotonic**
safety repair, and its manifest binds a reviewed parent sanitized report, the
former precise hard violation, a fixed case and arm, an allowlisted source diff,
and a machine-checked postcondition. Any mismatch fails closed before a model
call; a delta cannot resume an older attempt.

`activation-claim-v1` is currently the sole approved manifest. It confirms the
candidate `phased-current-boundary` repair that forces
`activation_status: "unverified"`. Its provider budget is exactly **3 attempts
/ 3 turns**. The result is a narrow evidence bridge: it has no paired
performance comparison and cannot independently replace the parent full
qualification. The parent and delta reports both require review and trusted
maintainer attestation before release.

Historical reports keep their original case and instruction digests. Never rescore an older run against a newer contract revision. The runner recomputes the canonical path-and-SHA-256 manifest before execution and fails closed when the instruction package no longer matches its declared digest.

## Process protocol

Each `start_attempt` or `execute_turn` is one process invocation:

1. The host writes one UTF-8 JSON object to stdin.
2. The driver writes one UTF-8 JSON object to stdout and exits with code `0`.
3. `start_attempt` returns a fresh, opaque `context_id` bound to the supplied `attempt_nonce`.
4. Later turns return the same nonce and context. A mismatch, reused context, malformed JSON, non-zero exit, timeout, or oversized output invalidates the attempt.

The normative shape is [adapter-protocol.schema.json](adapter-protocol.schema.json). The default timeout is 120 seconds per invocation and the default combined stdout/stderr limit is 1 MiB. Hosts may lower either limit. Provider sessions, credentials, and retry policy remain driver-owned.

## Trusted configuration boundary

The executable is configured by the CLI or MCP host as an absolute path plus separate argv items. The adapter always uses `shell=False`. On Windows, configure a native executable rather than a PowerShell or batch wrapper. Model/MCP requests cannot submit an executable, path, environment, command string, or adapter kind; they carry only an authorization reference and sealed-case reference. Environment variables are inherited from the trusted host process and are never accepted from model arguments.

The Codex driver creates a fresh `HOME`, `CODEX_HOME`, and empty workspace for every attempt. Plugins and bundled Skills are disabled, personal configuration is ignored, and authentication is copied into the isolated home only around one process invocation before being deleted in `finally`. This is required for a defensible no-router baseline.

The comparison arms receive the same structured Skill catalog. Each descriptor contains a canonical ID, description, domains, stages, and baseline availability. A public case may add a verified capability snapshot that changes activation readiness without changing semantic Skill intent. The Router instruction package is the only permitted difference between baseline and candidate.

## Protected artifacts and safe diagnostics

The runner creates and verifies `restricted/` before writing raw evidence. `restricted/checkpoint.json`, `restricted/raw-results.json`, attempt transcripts, failure diagnostics, and temporary authentication use fail-closed host permissions: POSIX mode checks or a protected Windows DACL limited to the current user and SYSTEM. An unprotected transcript is not eligible for resume.

If an output root contains any existing entry, preflight stops before the first attempt. Legacy public `checkpoint.json` or `raw-results.json` receive a dedicated integrity error. Use a new empty output root; the runner never hides a stale sanitized report or raw evidence behind a new protection claim.

Only `sanitized-report.json` remains in the public output root. Its `case_diagnostics` contains case IDs, counts, match rates, and candidate-minus-baseline deltas. It never includes prompts, expected or actual Skill values, rationales, or route payloads. Raw evidence remains local and restricted.

Preview a reference-driver configuration:

```powershell
$Python = (Get-Command python).Source
workflow-skill-router evaluation run `
  --profile behavior `
  --evidence-class reference-driver `
  --adapter subprocess `
  --adapter-executable $Python `
  --adapter-arg evaluation/v2/reference_driver.py `
  --repeats 3
```

For a real Behavior or Outcome run, use `--evidence-class fresh-model-execution` and explicitly add `--confirm-live-run`. This confirmation matters because providers may incur quota, latency, or monetary cost. The CLI prints a dry-run manifest before execution orchestration consumes it.

## Requalifying current Codex models

As of 2026-10-19, the [official model guidance](https://learn.chatgpt.com/docs/models)
positions `gpt-6.1-sol` for general complex work, `gpt-6-astra` for the most
demanding work, and `gpt-6-luna` for focused repeatable work. Availability is
account- and client-dependent. These are evaluation candidates, not new Router
qualification results. Historical `gpt-5.6-sol` reports keep their original model.

Freeze a clean source commit and adapter digest after local gates pass. Start
with a separately authorized `beta-smoke --screening --repeats 1` comparison:
6 cases × 2 arms = 12 attempts and 14 model turns per model; all three models
total 36 attempts and 42 model turns. Use a separate empty output directory per
model and pass the exact model through the Codex driver's `--model` argument.
Pass `--reasoning-effort` to the driver and record the CLI version. The isolated
client speed remains its default; no personal configuration is loaded. Do not compare
unrecorded defaults as if they were controlled model settings.

Screening reports use the locked `exploratory-model` evidence class and
`qualification_eligible: false`; repeated-run consistency is unavailable.
This is a screening run, not the three-repeat full qualification. The existing
behavior harness measures routing-contract behavior; it does not establish real
Skill activation, token savings, or completed-task quality. Those require
separate observable receipts and an outcome protocol. No live run is authorized
by this preparation note.

### 2026-10-19 本機探索性比較（待人工審查）

使用隔離的 Codex CLI `0.163.0`、固定 `medium` 推理設定，以及相同的六個案例與 Skill catalog。每個模型、每個 arm、每個案例只執行一次；這不是模型能力排名，也不是三次重複的正式資格測試。模型識別來自 CLI 設定，供應端沒有另外提供模型 snapshot 證明。兩組都不執行實際開發工作；candidate 的同意續接使用本機確定性狀態機，沒有證明完整 MCP／Host 整合或真實 Skill 啟用。

第一輪使用原有 Contract 2.3.0，結果完整保留：

| 模型 | 未使用 Router：最終路由欄位符合 | 使用 Router：最終路由欄位符合 | 輸入 Token 變化 |
| --- | ---: | ---: | ---: |
| GPT-6.1 Sol | 4 / 6 | 4 / 6 | +26.32% |
| GPT-6 Astra | 4 / 6 | 4 / 6 | +26.44% |
| GPT-6 Luna | 4 / 6 | 3 / 6 | +27.62% |

第一輪發現兩個前提問題：同意案例未明確提供既有 phased workflow；跨專案案例沒有既有 Native Goal 綁定，卻要求 `progress`。這些分數只能用來診斷，不能據此宣稱模型優劣。Luna 另遇到一次服務容量不足；失敗紀錄保留，續跑重用八筆完整結果，只重新執行中斷及未執行的案例。

Contract 2.3.1 補齊上述前提，並在兩份發行用 SKILL 中釐清外層 workflow 與目前 Phase／Work Item，以及 managed envelope 與 Native Goal 綁定的差異。新的 GPT-6.1 Sol 對照結果如下；不得與 2.3.0 的分數相減，當成純粹的產品改善幅度。

| 指標 | 未使用 Router | 使用 Router |
| --- | ---: | ---: |
| 最終六個路由欄位全部符合 | 3 / 6 | 6 / 6 |
| 完整契約符合，含所有回合及證據代碼 | 0 / 6 | 3 / 6 |
| Hard violation | 0 | 0 |
| 輸入 Token（含快取） | 104,473 | 132,551 |
| 輸出 Token | 1,965 | 1,182 |

目前能支持的解讀：Router 有助於讓長期工作模式、目前 Work Item 的支援範圍與指定路由規則保持一致；簡單任務常是兩組都選對。第一輪三個模型都將跨專案工作改以 managed envelope 組織；Luna 也減少了該案例中超出目前規劃範圍的支援項目。這些是工作政策的一致性，不能直接等同程式品質提升。

仍需保留的限制：

- 新指引目前只在 Sol 做了成對重測，尚未重新驗證 Astra 與 Luna。
- 完整契約剩三個未通過案例，差異都在分類來源或理由代碼；不得宣稱正式資格通過。
- `capability-unavailable` 案例的 `auto`／`explicit-locked` 標籤仍涉及「使用者間接指定能力」的解讀；兩組都保留同一個不可啟用的必要能力，因此不能把標籤差異宣稱為能力選擇品質提升。
- 這個封閉評測完整載入 Router 指令套件，輸入量增加約 26–28%。真實 Codex 按需讀取參考資料時可能不同；本次沒有證明節省 Token、費用或完整任務時間。
- 每個案例只有一次觀測，沒有估計重複執行的穩定性；正式模型資格、真實開發 Outcome 與 Host Pilot 均未完成。

合計完成 48 個獨立 attempt、56 個模型回合，另保留一次容量失敗。四份原始 sanitized reports 與兩組比較摘要都保留在維護者本機的 `dist/evaluation/20261019-current-models/`；`integrity-receipt.json` 綁定報表雜湊、48 個唯一 nonce／context，並確認沒有留下登入暫存。原始逐回合回應留在受限目錄，尚未公開發布或人工簽署。公開版本的歷史 attestation 維持原狀。

## Freshness and failure handling

- Every repeat must create a distinct provider context; a driver must not reuse chat/session IDs.
- The nonce is supplied by the orchestrator and must be echoed unchanged.
- The opaque context is the only driver state returned to later turns.
- A failed or ambiguous attempt is evidence of failure, not a reason to relabel or silently synthesize output.
- When a trusted adapter is unavailable, export a manual bundle and keep the resulting evidence review-required.
