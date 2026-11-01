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

The published release is `v2.1.1`, a dependency security patch that inherits the `v2.1.0` Behavior gate because routing is unchanged. That gate is a fresh paired beta smoke run on the `v2.1.0` frozen source: 36 attempts across 42 model turns, run through the Claude Code driver with a Claude model. The `v2.1.0` maintainer attestation records the model and the results. The run had zero hard violations, but no attempt passed the full turn contract, so it is bounded release evidence, not a full-contract qualification pass. Codex models were not re-qualified. The bounded `gpt-5.6-sol` evidence belongs to `v2.0.0`, and `v2.0.2` inherited it; it is not `v2.1.0` evidence. The real local-work-loop and Host Pilots remain `protocol-frozen-awaiting-real-pilot`. No real Pilot task has been counted. Memory fixtures are not real-model evidence.
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

## Running the Behavior gate with Claude Code

`adapters/claude_code_driver.py` runs the same paired protocol through Claude
Code. It subclasses the Codex driver, so route validation, the public evidence
vocabulary, the consent state machine, protected transcripts, and failure
diagnostics are shared byte for byte. The runner treats both drivers as
canonical Behavior entrypoints; the Claude driver's adapter revision binds its
own bytes and the Codex driver it loads.

Each turn starts a fresh `claude --print --output-format json` process with the
route or consent schema passed through `--json-schema`, `--tools ""`,
`--strict-mcp-config`, `--disable-slash-commands`, and
`--no-session-persistence`. The process gets a new `CLAUDE_CONFIG_DIR`, home,
temporary directory, and empty workspace, so no user settings, Plugins, Skills,
`CLAUDE.md`, or MCP servers load. Telemetry, error reporting, and nonessential
traffic are disabled. Host session variables, including `ANTHROPIC_BASE_URL`,
are not forwarded.

Authentication is explicit. The driver accepts only `CLAUDE_CODE_OAUTH_TOKEN`
(created with `claude setup-token`, which uses a Claude subscription) or
`ANTHROPIC_API_KEY` from the environment, and refuses to start without one. It
never reads the desktop app's login or the user's Claude configuration. When
both are set, Claude Code prefers `ANTHROPIC_API_KEY`, which bills the API
account; unset it to keep the run on the subscription.

Usage follows the Codex fields: `input_tokens` is input plus cache creation plus
cache reads, and `cached_input_tokens` is cache reads. Record the Claude Code
version (`claude_code_version` in the report provenance) and the exact model.

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
$Python = (Get-Command python).Source
$Driver = (Resolve-Path "evaluation/v2/adapters/claude_code_driver.py").Path
$Claude = "<absolute path to claude.exe>"
$Source = git rev-parse HEAD
$Adapter = python -c "import runpy,sys; m=runpy.run_path('scripts/run-v2-benchmark.py', run_name='adapter_revision'); print(m['adapter_source_revision'](sys.executable, [sys.argv[1]]))" $Driver
python scripts/run-v2-benchmark.py --suite beta-smoke --evidence-class behavior `
  --adapter-executable $Python --adapter-arg $Driver `
  --adapter-arg=--claude-executable --adapter-arg $Claude `
  --adapter-arg=--model --adapter-arg claude-sonnet-5-5 `
  --adapter-arg=--timeout-seconds --adapter-arg 180 --timeout-seconds 240 `
  --repeats 3 --confirm-live-run `
  --authorized-source-revision $Source --authorized-adapter-revision $Adapter `
  --output-dir dist/evaluation/claude-behavior
```

The tree must be clean and `$Source` must be the frozen candidate. The paired
beta smoke is 36 attempts and 42 model turns and consumes Claude quota. Its
sanitized report stays `review-required` until a maintainer reviews and attests
it.

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

## Host fault lane

The Behavior gate proves routing decisions, not what a session does when the
Router runtime breaks: every turn runs with no tools and no MCP. The host fault
lane fills that gap. `scripts/run-host-fault-suite.py` loads the real Plugin
into a Host session, injects one fault per case, and scores the transcript and
the final JSON against the SKILL contract. Cases live in
`host-faults/cases.jsonl`, the output schema in
`schemas/host-fault-output.schema.json`, and the plan record in
`pilots/host-fault-plan.json`.

Every case asks for the same explicitly named Skill, so the route must keep
`selection_mode: explicit-locked` and that `primary_skill` whatever happens to
the runtime:

- `mcp-unavailable`: the staged Plugin copy sets `WORKFLOW_SKILL_ROUTER_HOST`
  to an unsupported value, so the real server exits before it serves tools.
- `tool-denied`: the Host's own permission system refuses `plan_work`. In
  Claude Code the run has no allow rule for the Router server and passes
  `--permission-prompts none`.
- `tool-failure`: `host-faults/fault_proxy.mjs` forwards every message to the
  real server and answers `plan_work` with the server's capability-unavailable
  error envelope.

A case passes when the session declares `runtime_binding: skill-only-fallback`,
reports the `mcp_outcome` its transcript shows, keeps the explicit Skill, names
`skill-only-fallback` in its rationale, never claims `hybrid-full`, uses no
tool outside the Router server, and stays within the attempt budget. The plan
record lists the hard violations. A case whose fault did not fire is `invalid`,
not failed; that is a harness problem.

Each attempt gets a fresh `CLAUDE_CONFIG_DIR` or `CODEX_HOME`, home, temporary
directory, workspace, and `WORKFLOW_SKILL_ROUTER_DATA_DIR`; only proxy settings
and the explicit auth variables are forwarded. Every execution calls a live
model, so the Behavior gate rules apply: `--confirm-live-run`, explicit auth,
and review of `sanitized-report.json` before any public claim. Reports carry
`evidence_class: host-fault-behavior` and `qualification_eligible: false`;
they never count toward the Behavior gate or a Host pilot. Transcripts stay
under `protected/`.

```powershell
$Claude = "<absolute path to claude.exe>"
python scripts/run-host-fault-suite.py --client claude-code --executable $Claude --print-plan
python scripts/run-host-fault-suite.py --client claude-code --executable $Claude `
  --model claude-sonnet-5-5 --confirm-live-run --output-dir dist/evaluation/v2/host-faults
```

The Claude Code command was checked against Claude Code 2.1.309 (`--plugin-dir`,
`--permission-prompts none`, `--tools ""`, stream-json). The Codex command is
constructed but unexercised: whether `approval_mode = "approve"` under
`approval_policy = "never"` denies the call, and whether `--ignore-user-config`
still loads `CODEX_HOME/skills`, are settled at the first authorized run. A
stale-snapshot fault is deferred because `plan_work` returns no freshness
field; a proxied payload would be one the real server never emits.

## Instruction-loading screening

The benchmark keeps `--instruction-loading full` as its default. The opt-in
`--instruction-loading core` ablation loads the unchanged standalone SKILL and
the public reason-code vocabulary, without preloading the four reference
documents. Its separate manifest seals both paths and content hashes. The Skill
catalog, task inputs, output schema, execution mode, and scoring contract stay
the same.

Core loading requires `--screening`, so it cannot qualify a release or be used
for Delta Qualification. Reports record the loading mode and instruction digest.
An offline check that does not invoke a model is:

```powershell
$evaluationPython = (Get-Command python).Source
python scripts/run-v2-benchmark.py `
  --suite beta-smoke --screening --repeats 1 `
  --instruction-loading core --evidence-class reference-driver `
  --adapter-executable $evaluationPython `
  --adapter-arg evaluation/v2/reference_driver.py `
  --output-dir dist/evaluation/core-reference
```

Live runs still require explicit model/quota authorization, a fixed budget,
`--confirm-live-run`, and the source/adapter integrity checks.

### 2026-10-20 exploratory comparison

One paired run used the same six Contract 2.3.1 cases, GPT-6.1 Sol at `medium`,
and Codex CLI `0.163.0-alpha.10.2`. Consent continuations used the existing local
deterministic transition. Each case ran once per arm: 12 attempts and 14 CLI
turns. The configured model identifier is not a provider-attested snapshot.

| Observation | Full package | Core-only package |
| --- | ---: | ---: |
| Instruction bytes, UTF-8 | 18,712 | 8,150 |
| Final routing fields match | 6 / 6 | 6 / 6 |
| Full evidence contract match | 1 / 6 | 1 / 6 |
| Hard violations | 0 | 0 |
| Input tokens, including cached input | 132,349 | 115,993 |
| Output tokens | 1,382 | 1,474 |

Core-only input was 12.36% lower than the full-package arm. No regression in
final routing fields was observed in this single run; both arms still failed
the full evidence contract on five cases. This does not establish repeatability,
lower monetary cost, faster completed development, or release qualification.

The installed Plugin already supports reading references as needed. This
closed routing test omits references entirely; it does not simulate on-demand
retrieval and cannot establish installed Plugin token savings. The tested
instruction bodies and Plugin runtime remain unchanged. Local manifests and
restricted transcripts are retained under
`dist/evaluation/next-round/run-03/`; evidence remains review-required.

繁中說明：這次量到的是評測指令包的輸入減量，完整與精簡組的最終路由都是
6/6，但完整契約都只有 1/6。尚不能宣稱正式 Plugin 已節省 Token、提高程式品質，
或通過新版模型資格驗證。

### Historical development replay: blocked before usable outcomes

Two replay tasks were bound to actual Router Core repair commits:
`86f139f8946afa2578c0ba3be915097be15eefbf` for explicitly selected Skills in
Single work/replay, and `30a9d4cf84c4e14faa688f0a39c86086da37c464` for bilingual
classification and negated long-running intent. Inputs used each repair's
parent source snapshot. Held-out regression checks failed before each repair
and passed at its known fix. The first task's checks cover explicit selection,
replay, and unchanged generic automatic work; they do not qualify the entire
historical integration suite.

The first Codex CLI `0.163.0-alpha.10.2` baseline attempt timed out after
300 seconds. A second baseline attempt, using the `:workspace` permission
profile and an outside-repository workspace, was stopped after about 125
seconds without a completed shell command or a source repair. Independent
non-model sandbox commands succeeded, but model-driven shell execution did not.
The cause was unresolved at that point. The later execution recovery below
isolated fresh sandbox initialization against the shared temporary directory;
the earlier failed attempts remain failed and are not rescored.

One diagnostic disabled the code-mode host and received an explicit
host-disabled error; that diagnostic cannot establish a normal-client failure.
A subsequent diagnostic restored the normal execution features and still
failed to create the marker file within its 75-second bound. The installed
`0.145.0` client was also checked without changing the requested model; it
returned HTTP 400 saying that `gpt-6.1-sol` was unsupported with ChatGPT account
authentication. This older-client rejection is not a claim that the newer
client or the account generally lacks the model: the routing run above used it
successfully.

The alternative local gRPC transport was also checked with the same workspace
permissions and failed its bounded marker check. Full-agent development
comparisons were stopped. **Usable completed full-agent workflows in that
round: zero.** The
bounded patch-generation fallback below is a separate experiment and does not
establish agent-run testing, installed Plugin/MCP integration, or verified-Host
conformance. All these replays add zero tasks to the formal twenty-task Pilot.

The exploratory run retained 12 completed routing attempts, two incomplete
development attempts, four compatibility diagnostics, and six bounded patch
attempts: 24 execution attempts in total. Incomplete turns have unavailable
usage, not zero usage. Protected local artifacts remain under
`dist/evaluation/next-round/`; temporary authentication files were removed.

### Bounded patch-generation fallback

The fallback used the same GPT-6.1 Sol, `medium` reasoning, and
`0.163.0-alpha.10.2` client in fresh contexts, without model tool execution.
Each of the two historical tasks ran once in each of three arms. All arms
received the same complete source files and task brief. The host accepted only
unique exact replacements in the task's source-file allowlist, applied edits
transactionally to isolated snapshots, and ran held-out tests afterward.
Scope escape, missing-match, and transactional-failure checks passed before the
first model run. No golden repair or held-out test body was sent to the model.

| Observation | Model only | Full Router instructions | Core Router instructions |
| --- | ---: | ---: | ---: |
| Patches applied | 2 / 2 | 2 / 2 | 2 / 2 |
| Cases passing all held-out checks | 1 / 2 | 1 / 2 | 1 / 2 |
| Input tokens, including cached input | 51,101 | 60,763 | 55,327 |
| Output tokens | 2,390 | 3,127 | 3,214 |

All three arms repaired the explicitly selected Skill/replay defect and passed
its two focused checks. All three passed 28 of 29 bilingual-classification
checks and missed the same remaining case: recognizing resumable intent in
`跨專案分里程碑執行，保留進度以便恢復`. These generated repairs were tested only in
isolated historical snapshots; the already-fixed current source was not
replaced.

Core input was 8.95% below the full arm but 8.27% above model-only input. This
small experiment does not demonstrate better repair correctness from Router
instructions or token savings over the model-only arm. The task briefs were
reconstructed from repair scope, rather than untouched original issue reports;
they did not enumerate every lexical alias, which limits interpretation of
the shared classification miss. There was no repeat per task/arm and no
generalization or code-quality claim. The host ran the tests; the model did not.

The frozen manifest, script binding, six patches, and test output remain local
under `dist/evaluation/next-round/patch-repair-01/`. They are exploratory and
await human review. This fallback did not establish CLI tool-execution
recovery or qualify the formal real-work Pilot.

繁中說明：受限修補比較已完成，三組都是 1/2 案例完全通過，沒有證明 Router
能提高這兩個問題的修補正確率。精簡組比完整組少用約 8.9% 輸入 Token，
但仍比原生組多約 8.3%。這個受限修補實驗本身沒有驗證完整代理流程或正式
Plugin 效能；後續完整代理結果見下節。

### Full-agent execution recovery and one paired repair

The 2026-10-20 follow-up used the same `0.163.0-alpha.10.2` client and
GPT-6.1 Sol with `medium` reasoning. A no-model crossover isolated the startup
stall to fresh Windows sandbox state interacting with the shared temporary
directory. Giving each attempt its own `TEMP`, `TMP`, and `TMPDIR` restored
command execution without disabling the sandbox or code-mode host. The
evaluation CLI driver now creates and protects that directory per attempt.
A fresh live-model smoke wrote and read a real file and ran unittest in
19.48 seconds.

Python's private temporary directories exposed a second compatibility issue
in the legacy `unelevated` sandbox. The three installed Python runtimes
reproduced access-denied errors. The existing, already-provisioned `elevated`
sandbox passed the same file lifecycle check, so the complete repair runs used
that sandbox with workspace permissions. No sandbox accounts were provisioned
and no full-access workaround was used. See the official
[Windows sandbox guidance](https://learn.chatgpt.com/docs/windows/windows-sandbox).
The normal evaluation driver still isolates its Codex home; the complete-agent
replays reused the existing sandbox home, disabled user configuration, rules,
plugins, Memory, project instructions and the discovered standalone Skills,
then supplied the same two small test Skills in each fresh source snapshot.
This is fresh-thread evidence, not a claim of a fully hermetic host.

One bilingual-classification repair ran once per arm against the same
historical source, brief, and held-out checks. Unlike the earlier patch-only
fallback, both agents inspected and edited real files and ran their own tests.
The brief now explicitly included `跨專案分里程碑執行，保留進度以便恢復` as an
acceptance example; this is a new experiment, not a retrospective improvement
of the earlier score.

| Observation | Model only | Router Skill + bundled MCP |
| --- | ---: | ---: |
| Held-out regression checks | 29 / 29 | 29 / 29 |
| Completed shell commands | 7 | 14 |
| Elapsed seconds | 158.875 | 335.372 |
| Input tokens, including cached input | 213,137 | 702,659 |
| Cached input tokens | 164,608 | 644,096 |
| Output tokens | 4,141 | 6,935 |

This pair shows **no repair-correctness gain**. Router input and latency were
higher. Neither token savings nor a general speed or quality improvement is
supported by this single pair. The Router arm also ran a much broader
historical suite: its first broad run had 43 errors, five revision-expectation
failures and 13 skips among 566 tests. Its focused routing and integration
checks subsequently passed, but the whole historical suite did not. The
held-out result above covers only the 29 task-specific checks.
The different amount of work and provider caching also prevent interpreting
these figures as an isolated Router-overhead estimate or a billing comparison.

The Router arm made real MCP calls. Its Profile-less Phased plan returned
`decomposition-required`, with no executable item. The model nevertheless
tried invented boundary IDs in `record_work_event` and `evaluate_gate`; both
failed closed. That is an integration/usability defect, not a completed local
workflow or evidence of Host authority. A separate earlier repair completed
through direct Python imports instead of MCP and is excluded from this pair's
Plugin-integration claim. Another configuration diagnostic was stopped before
source edits. Neither is silently counted as an MCP success.

The resulting development changes expose the six actual observation shapes
in the MCP input schema, reject mixed or unknown payloads before bridge
dispatch, explain the local evidence digest, and make the decomposition
boundary actionable. They also distinguish absent managed Profile directories
from invalid existing Profiles: a new installation no longer receives a false
`managed-profile-invalid` warning. The existing strict I/O and authority checks
remain in force.

The rebuilt development bundle then completed a separate Profile-backed
integration replay of the explicit-Skill retention defect. A frozen workspace
Profile supplied `repair` and `review` phases with separate Primary Skills and
exit checks. The model edited the historical source, reproduced the regression
before repair, and ran 42 focused integration tests afterward. Both held-out
checks passed. All 11 actual MCP calls succeeded, including two
`evaluate_gate` calls with `passed=true` and `host_transition_authorized=false`.
Read-only SQLite verification confirmed both work items were `completed`,
with two persisted `gate-pass` transitions and no Native Goal binding. The
Profile and measured bundle hashes still matched the frozen inputs.

That run took 198.273 seconds, with 526,135 input tokens including 477,824
cached input tokens, and 3,752 output tokens. Its transcript and validation
remain under `dist/evaluation/next-round/agent-profile-replay-01/`; a sanitized
machine-checked readback is in
`dist/evaluation/next-round/sanitized-agent-workflow.json`. This verifies a
complete local workflow under the configured Profile. It is **not** a paired
before/after optimization score: the task and Profile differ from the
Profile-less bilingual repair above. It does not establish that schema changes
alone caused better completion or that an unconfigured Phased plan now
decomposes automatically.

The paired manifest, transcripts, patches and held-out output are retained
under `dist/evaluation/next-round/agent-replay-03/`. These runs used the
canonical Skill and actual bundled MCP transport configured in the test
environment. They do **not** verify marketplace installation, verified-Host
activation, Native Goal transitions or a published Plugin upgrade. They remain
exploratory, review-required, and contribute zero tasks to the formal Pilot.

繁中說明：CLI 已能實際讀寫檔案、修改程式並自行跑測試。這一組對照兩邊都是
29/29，Router 組花的時間與輸入 Token 較多，不能宣稱提高程式正確率、加速或
省 Token。實測找到的是工作流程介面的缺口：未分解的 Phased 計畫不能當成可
執行工作，也不能捏造工作 ID 通過 Gate。這輪優化針對輸入契約、失敗指引與
首次使用的誤報；正式模型資格驗證與 marketplace 安裝驗證仍未完成。
另外一個設定好 workspace Profile 的實測，已由模型實際完成修補、42 項測試、
兩個階段與兩個本機 Gate；11 次 MCP 呼叫全部成功，資料庫也確認兩個工作項目
完成。可證明的是設定後的流程能被持久保存與核對，不能把不同條件的案例當成
優化前後的效能提升。

## Freshness and failure handling

- Every repeat must create a distinct provider context; a driver must not reuse chat/session IDs.
- The nonce is supplied by the orchestrator and must be echoed unchanged.
- The opaque context is the only driver state returned to later turns.
- A failed or ambiguous attempt is evidence of failure, not a reason to relabel or silently synthesize output.
- When a trusted adapter is unavailable, export a manual bundle and keep the resulting evidence review-required.
