# Workflow Skill Router V2

[繁體中文](README.zh-TW.md) · [Documentation](https://huangchiyu.com/Workflow-skill-router/) · [Routing Flight Recorder](https://huangchiyu.com/Workflow-skill-router/#routing-flight-recorder)

Workflow Skill Router is a pre-execution, runtime-aware Skill-selection layer for Codex. It keeps the agent focused on the smallest verifiable execution path, preserves user authority, and exposes what the runtime can actually do. It is not a substitute for permissions, approval policies, sandboxing, or production orchestration.

> Current V2 release: `2.0.1`. The immutable V1.3.1 recovery path remains available during migration.

Every V2 release is source-bound. A candidate starts as `prepared-local-candidate`; only a reviewed metadata-only promotion that binds `release_source_revision`, records maintainer attestation, and sets `release_lifecycle` to `reviewed-attested-publishable` can unlock `CREATE_V2_RELEASE`. The trusted default-branch workflow then builds, tags, attests, and publishes the frozen source.

## 60-second outcome

Give the Router a request. It returns an execution envelope, a capability plan, the consent boundary, and the evidence needed to continue safely. The public Flight Recorder shows the exact sanitized MCP request and response instead of recreating the decision in the browser.

```text
Request
  -> classify work shape
  -> discover usable runtime capabilities
  -> lock explicit user choices
  -> plan the smallest route
  -> execute, verify, and disclose actual SKILL usage
```

## Plugin + MCP versus Skill-only

| Capability | Plugin + MCP | Skill-only |
| --- | --- | --- |
| Routing instructions | Included | Included |
| Personal Routing Profile | Deterministic load, validation, precedence, and preview | Advisory interpretation of the same fixed JSON contract |
| Local durable R0 planning and scoped consent | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Not observable |
| Verified-host scheduling and route validation | Available after host integration | Unavailable |
| Cross-process state and compare-and-swap | Host/runtime dependent | Unavailable |
| Sealed model evaluation | Configured adapter required | Manual workflow only |
| Honest runtime label | `bundled-local-r0` or verified profile | `skill-only-fallback` |

Choose the Plugin when Codex supports Plugin/MCP loading. Choose the standalone SKILL when you need instruction-only routing or must run in a host without Plugin support. The `hybrid-full` conformance label is unavailable to the standalone package.

## Five-minute Plugin + MCP quickstart

For a normal installation, pin the immutable `v2.0.1` marketplace snapshot:

```powershell
codex plugin marketplace add eric861129/Workflow-skill-router --ref v2.0.1
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
```

Open a new Codex task and ask it to show the Workflow Skill Router status. The published V2 surface exposes twelve MCP tools: **4 always local-ready**, **5 verified-Host-required**, and 3 configured-adapter-required tools. Runtime readiness remains authoritative for every individual operation.

For contributors who are changing or testing the Router:

```powershell
git clone https://github.com/eric861129/Workflow-skill-router.git
Set-Location Workflow-skill-router
codex plugin marketplace add .
codex plugin add workflow-skill-router@workflow-skill-router
codex plugin list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz doctor
```

The checkout is the source for the current V2 release. Contributors must keep the candidate and trusted release metadata distinct: the later metadata-only promotion binds `release_source_revision` to the exact reviewed source SHA before `Release V2` can dispatch.

`v2.0.1` is an immutable GA tag created and verified by the trusted release workflow; normal installations should pin that tag instead of a mutable branch.

The released Plugin already contains the MCP bundle and Python runtime. Node.js 24+ and Python 3.11+ are required; npm is needed only when rebuilding from source. See [Plugin installation](site/src/content/docs/guides/install-plugin.md).

## Five-minute Skill-only quickstart

For a normal installation, download [`workflow-skill-router-skill-v2.0.1.zip`](https://github.com/eric861129/Workflow-skill-router/releases/download/v2.0.1/workflow-skill-router-skill-v2.0.1.zip) and extract its inner `workflow-skill-router/` folder into the Codex Skills directory.

For contributors working from a checkout on Windows:

```powershell
$Target = Join-Path $env:USERPROFILE ".codex\skills\workflow-skill-router"
Copy-Item -Recurse -Force "starter\v2\workflow-skill-router" $Target
Get-Content -Encoding UTF8 (Join-Path $Target "SKILL.md") | Select-Object -First 8
```

This package preserves routing instructions and explicit-choice policy, but it cannot prove durable resume, full drift detection, or sealed activation. See [Skill-only installation](site/src/content/docs/guides/install-skill.md).

## Architecture: Runtime Capability Discovery first

Runtime Capability Discovery separates five facts that agents often collapse: installed metadata, host exposure, authentication, policy eligibility, and freshness. A capability becomes routable only when its risk-specific requirements pass.

```mermaid
flowchart LR
    U["User request"] --> R["Router core"]
    H["Codex host observations"] --> D["Runtime Capability Discovery"]
    P["Plugin handshake"] --> D
    S["SKILL metadata"] --> D
    D --> R
    R --> E["Single / Phased / Managed Goal"]
    E --> L["Local R0 control plane"]
    E --> V["Verified host adapters"]
    E --> M["Configured evaluation adapter"]
    V --> A["State, evidence, and audit stores"]
```

Maintainers can start with [the V2 architecture overview](docs/architecture/v2-overview.md).

## Single, Phased, and Managed Goal

- **Single** handles one bounded intent with one minimal primary capability.
- **Phased** preserves distinct stages and reroutes each phase from current evidence.
- **Managed Goal** maintains a resumable work graph, respects dependencies, and treats the Codex Goal as host-owned state.

The Router does not force every task into Goal orchestration. Work shape comes from the request, dependencies, risk, and current Goal relation.

`plan_work` combines **deterministic automatic classification** for the work envelope with an **optional deterministic Profile** for a user-owned Skill Tree. The classifier is a bounded structural and lexical ruleset, not a semantic model; its source, confidence, revision, and reason codes are returned separately from the Profile match source. Planned Skills remain intent only and actual activation stays `unverified`. Explicit Skill Lock and consent boundaries still apply. The local Router does not activate Skills, mutate a native Codex Goal, or grant deployment/production authority.

## Explicit Skill Lock

When the user names a SKILL, that choice becomes authoritative. The Router may recommend support, but it must explain the purpose, scope, refusal consequence, and context cost before activation. Rejected support stays out of active selections.

In Plugin mode, the proposal is persisted before the question is shown. A follow-up model turn classifies only `approved`, `rejected`, or `unclear`; the deterministic MCP transition preserves the bound route and fails closed if Phase, scope, revision, or material context changed. Skill-only mode keeps the same interaction policy as advisory instructions, but cannot claim durable enforcement.

When the user names no SKILL, the Router chooses the smallest sufficient route without repeatedly asking for consent to its own recommendations. Before execution it declares planned SKILL usage; after execution it reports actual usage and any change.

## Personal Routing Profiles

V2 keeps the most valuable part of V1: you can own the Skill Tree. A Personal Routing Profile maps objective keywords, domains, tags, and work modes to a phased route with one Primary, up to three current-phase support SKILLs, and an exit gate per Phase.

> Personal Routing Profiles ship in `v2.0.0-beta.2`. The 36-attempt beta.1 Model Evaluation is historical runtime evidence and does not cover this Profile feature.

Precedence is deterministic: host hard constraints, the user's explicit SKILL for the current request, workspace profile, personal profile, then built-in routing. A workspace profile lives at `.codex/workflow-skill-router.json`; personal profiles live under the external Router data directory. MCP workspace reads are accepted only under a Client-advertised root or `WORKFLOW_SKILL_ROUTER_WORKSPACE_ROOTS`; a model-supplied arbitrary path fails closed. A matched workspace tree replaces the personal tree as one complete route—no implicit deep merge.

```powershell
Copy-Item starter/v2/workflow-skill-router/assets/personal-routing-profile.example.json ./my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile validate .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile install .\my-profile.json
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile list
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile preview --objective "Deliver the API" --work-mode phased --domain api --explain
python plugins/workflow-skill-router/runtime/workflow_skill_router.pyz profile lint .\my-profile.json
```

The generated Plugin runtime supports `profile preview --explain` and `profile lint`; both are deterministic diagnostics and expose no SKILL instruction body or authority. Plugin + MCP mode loads and validates profiles deterministically. Skill-only reads the same contract as `skill-only-fallback` only when the Host grants filesystem access to the fixed Profile locations; otherwise the user must provide the Profile content in the conversation. It cannot claim durable loading or enforcement. In both modes, a profile result is `intended-unverified`: Runtime Capability Discovery still decides whether each SKILL is installed, exposed, compatible, authorized, and eligible. A profile never installs a SKILL or grants permission. See [Personal Routing Profiles](site/src/content/docs/concepts/personal-routing-profiles.md).

## MCP tool surface

The Plugin exposes twelve typed tools:

```text
sync_runtime_context       plan_work                  propose_support_consent
transition_support_consent get_next_work              validate_route
record_work_event          evaluate_gate              get_router_status
run_model_evaluation       compare_evaluations        export_router_artifact
```

Tool schemas, risk, required capabilities, and fallback actions are generated from the same contracts used by the server. See the [generated MCP reference](site/src/content/docs/reference/mcp-tools.mdx).

## Runtime readiness matrix

### Published beta.3 (`published-beta.3`)

| Availability | Tools | Meaning |
| --- | --- | --- |
| `local-ready` | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Four bundled Router-local operations |
| `verified-host-required` | `sync_runtime_context`, `get_next_work`, `validate_route`, `record_work_event`, `evaluate_gate` | Five operations require verified Host authority |
| `configured-adapter-required` | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Three operations require an authorized evaluation adapter |

### Prepared GA candidate (`prepared-ga-candidate`)

This prepared candidate matrix is **not included in published beta.3** and is not a released GA version. It remains blocked by the checked-in `prepared-local-candidate` lifecycle until the exact candidate SHA has fresh final model evidence, maintainer attestation, review, and a trusted metadata-only source binding.

| Availability in bundled local R0 | Tools | Meaning |
| --- | --- | --- |
| `local-ready` | `plan_work`, `propose_support_consent`, `transition_support_consent`, `get_router_status` | Durable local R0 planning, scoped consent, and status |
| `conditional-local` | `get_next_work`, `record_work_event`, `evaluate_gate` | Router-owned graph scheduling, reported local progress, and advisory local gate evaluation only |
| `verified-host-required` | `sync_runtime_context`, `validate_route` | Needs verified host authority and stores |
| `configured-adapter-required` | `run_model_evaluation`, `compare_evaluations`, `export_router_artifact` | Needs an authorized evaluation adapter and evidence |

The prepared GA candidate claim is deliberately **4 always local-ready + 3 Router-owned conditional-local**, never `7/12 local-ready`. A conditional-local call succeeds only for a validated Router-owned work graph with no Native Goal authority. `get_next_work` returns `authority_mode=router-local` and `host_goal_mutated=false`; progress and local gate results use `evidence_class=user-or-agent-reported-local` and `host_transition_authorized=false`. A local gate pass is advisory: it is not Skill activation, Native Goal completion, deployment approval, or production permission. Explicit Skill Lock and consent behavior are unaffected.

| Runtime condition | `get_next_work` | `record_work_event` | `evaluate_gate` |
| --- | --- | --- | --- |
| Valid Router-owned graph | Router-local result | Router-local reported progress | Router-local advisory gate |
| Native Goal | `verified-host-scheduler` | `verified-event-store` + `activation-receipt-verifier` | `verified-evidence-store` + `gate-authority` |
| Missing Router-owned graph | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally | `router-owned-work-graph`; create or replay locally |
| Corrupt Router-owned graph | Sanitized `internal-error` | Sanitized `internal-error` | Sanitized `internal-error` |

A missing graph is a local graph-initialization condition, not a reason to invent a Host fallback. A corrupt graph crosses an integrity boundary and returns only a public-safe correlation through `internal-error`; internal corruption details remain in diagnostics. Native Goal work uses the tool-specific verified Host capability shown above. Every unavailable or unsafe branch must **fail closed**.

Unavailable calls return a typed `capability-unavailable` response with required capabilities and a fallback action. The Router never fabricates a successful scheduler or evaluation result. The `latest` compatibility channel remains on V1.3.1 until the V2 GA gate is passed.

## Real Model Evaluation

**Tier 0 Contract** fixtures prove deterministic compatibility; they are not model behavior. Behavior evidence requires fresh isolated attempts, a sealed case package, paired baseline/candidate manifests, bounded output, zero hard violations, and trusted review before publication. The baseline arm is explicitly `model-only`; the candidate is `hybrid-router`. For consent follow-ups, the fresh model classifies intent and the persisted MCP state machine materializes the final route.

Evaluation contract `2.3.0` preserves the current-Phase oracle and stateful Phase-transition scoring, then binds every Behavior run to a clean full source revision and a verified adapter entrypoint identity. The runner revalidates the source and adapter before and after each adapter invocation, so a changed source or copied, renamed, or substituted adapter cannot continue an existing run. Its six-case beta profile remains 36 attempts and 42 model turns; the thirteen-case full gate is 78 attempts and 96 model turns at three repeats per arm. Historical `2.2.0` reports retain their original case and instruction digests and are never rescored against the newer contract. Before a fresh authorized `2.3.0` run, public evidence remains `manual-required`; after execution it remains `review-required` until trusted attestation.

## Security boundary and local state

Plugin installation, SKILL consent, runtime permission, and production authorization are separate decisions. The model cannot supply executable paths for evaluation, mint host authority, upgrade a fixture into runtime evidence, or mutate the native Codex Goal.

The Plugin stores state outside its cache:

| Platform | Default path |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Codex\workflow-skill-router` |
| macOS | `~/Library/Application Support/Codex/workflow-skill-router` |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/codex/workflow-skill-router` |

Set `WORKFLOW_SKILL_ROUTER_DATA_DIR` to choose another external directory. No telemetry is enabled by default. Read the [security boundary](site/src/content/docs/reference/security-boundaries.md) before integrating host-side R2/R3 actions.

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md), then run the focused checks for the surface you changed. Release artifacts come from allowlists and deterministic builders; generated outputs are never edited by hand.

```powershell
$env:PYTHONPATH = (Resolve-Path "packages/router-core/src").Path
python -m unittest discover -s packages/router-core/tests -v
python -m unittest discover -s tests -v
python scripts/build-v2-demo-data.py --check
$Version = (Get-Content -Raw -Encoding UTF8 release/version.json | ConvertFrom-Json).v2_version
$Output = Join-Path "dist" "release-$Version"
python -I -S -B scripts/build-release-artifacts.py --output-dir $Output --provenance-mode test --check-determinism
```

The release builder allows repeatable overwrites only for the current manifest. It fails closed if the output directory contains a stale, unexpected, symlinked, or otherwise unmanifested path; use a version-specific directory instead of mixing release generations.

## Version channels

| Channel | Current role | Promotion rule |
| --- | --- | --- |
| `latest` | V1.3.1 compatibility until V2 GA | Moves only after the GA release gate |
| `latest-v1` | Immutable V1 recovery | Remains pinned to V1.3.1 |
| `latest-v2` | Historical V2 prerelease channel | Retains reviewed prerelease history until the qualified GA promotion |

The repository is V2-first even while the compatibility channel remains pinned. Version metadata lives in [`release/version.json`](release/version.json).

## V1 migration

Use the [V1 to V2 migration guide](site/src/content/docs/guides/migrate-v1-to-v2.md) to move from template-based routing to the runtime-aware Plugin or standalone SKILL. V1 source and packages remain recoverable from the immutable [`v1.3.1` tag](https://github.com/eric861129/Workflow-skill-router/tree/v1.3.1) and GitHub Release; they are not primary V2 navigation.

MIT licensed.
