# Workflow Skill Router V2 Routing, Explicit Lock, and Consent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作可驗證的 Single／Phased／Managed Goal 分類、跨規模 Explicit SKILL Lock、scope-aware consent、selection authority／manifest trust，以及只能對有效 Route 簽發的短效 execution lease。

**Architecture:** Model Semantics Plane 提交 typed request signals、directive 與 route proposal；Python core 依 deterministic policy 驗證，不接受 client 偽造 forced origin。Explicit SKILL 是覆蓋所有 envelope 的 policy overlay；中型任務仍保留 Phase Plan，每個 Phase 重路由但繼承 lock，support consent 預設只涵蓋 current Phase，拒絕後只能限縮結果或 honest block。

**Tech Stack:** Python 3.11+ standard library、`unittest`、immutable `dataclasses`、`enum.StrEnum`、`hashlib`、`hmac`、`datetime`

## Global Constraints

- 唯一 runtime distribution 與 import namespace 分別為 `packages/router-core/` 與 `workflow_skill_router.*`；本計畫只建立／修改 `routing/` 及其 tests。
- Consumes plan 01 的 immutable `CapabilitySnapshot`、`Capability`、`Availability`、`RiskLevel`、`canonical_json()`；不得另建第二份 capability model。
- 任務規模、Goal relation、Skill policy、risk 與 runtime mode 互相正交。Explicit SKILL 不得把 phased 壓成 single，也不得把 managed Goal 壓成單一路由。
- `goal_relation=status` 必須產生 `control-query` 且沒有 routing payload；active Goal 的 `side-question`／`unrelated` 不得被誤判為 managed-goal progress。
- 使用者指定 SKILL 優先。`required_all`、`allowed_set`、`preferred_primary` 都要做 scope-level coverage；「只用 X」固定為 `allowed_set + support_policy=forbid`。
- 只有 `router-recommended` support 需要 consent；`system-required`、`developer-required`、`safety-runtime-required` 必須由 server-side authority resolver 根據 immutable policy snapshot／verified directive 派生，client 宣告不得直接信任。
- 在 consent 前，不得讀取、載入、遵循或呼叫 support SKILL／其專屬能力。每個 scope proposal 最多三個不同 support SKILL。
- Consent 不是 runtime approval；安裝、登入、connector、遠端或 privileged 行動仍須 host approval。
- Replan／reroute／replacement Phase 必須保留 semantic scope anchor；新 Phase ID 不得解除 lock、grant 或 rejection。
- 拒絕後，相同 capability＋purpose class＋scope anchor＋material context fingerprint 不得重問。能力不足時保留原 exit gate，只能 `limited` 或 `blocked`，不得製造完成。
- Route 必須綁定 immutable snapshot；R2／R3 簽 lease 前要 fresh preflight、runtime approval、state version 與 action digest。
- Execution lease 短效、不可擴權；每次 invocation 都重驗 capability、fingerprint、purpose、state version 與 expiry。
- 所有資料、測試名稱、錯誤訊息與註解使用 UTF-8 繁體中文；core 不新增第三方 runtime dependency。
- Persistence、Phase state transition、Goal Work Graph、MCP transport 由後續計畫實作；本計畫只輸出純函式／immutable contracts 給它們使用。

## Locked File Map

```text
packages/router-core/src/workflow_skill_router/routing/
├── __init__.py       # public routing exports
├── models.py         # RequestDecision、policy、Route、lease contracts
├── directives.py     # typed user directive normalization
├── profiler.py       # goal short-circuit and envelope classification
├── scope.py          # semantic ScopeAnchor inheritance
├── coverage.py       # explicit skill disposition／completion coverage
├── consent.py        # proposal, grant, rejection, material matching
├── authority.py      # server-derived selection origin
├── trust.py          # SKILL manifest requirement trust boundary
├── validator.py      # route hard-policy validation
└── leases.py         # issue/use short-lived execution lease
packages/router-core/tests/routing/
├── test_profiler.py
├── test_explicit_lock.py
├── test_consent.py
├── test_authority_and_trust.py
├── test_route_validator.py
└── test_explicit_skill_scenarios.py
```

---

### Task 1: Normalize directives and select the routing envelope without false Goal escalation

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/routing/__init__.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/models.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/directives.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/profiler.py`
- Create: `packages/router-core/tests/routing/test_profiler.py`

**Interfaces:**
- Consumes: `RiskLevel` from `workflow_skill_router.capabilities.models`。
- Produces: `GoalRelation`、`ExecutionKind`、`RoutingEnvelope`、`RuntimeMode`、`ExplicitSemantics`、`SupportPolicy`、`DirectiveInput`、`UserDirective(requested_work_mode, ...)`、`TaskSignals`、`RoutingProfile(envelope, work_item_envelope_override, ...)`、`RequestDecision`；`resolve_directive(value: DirectiveInput) -> UserDirective`；`decide_request(goal_relation, signals, directive, runtime_mode) -> RequestDecision`。

- [ ] **Step 1: Write failing tests for status short-circuit, small, medium, Goal, and explicit-policy orthogonality**

```python
# packages/router-core/tests/routing/test_profiler.py
class RequestProfilerTests(unittest.TestCase):
    def test_status_is_control_query_without_routing_payload(self) -> None:
        decision = decide_request(GoalRelation.STATUS, TaskSignals.small(), UserDirective.auto(), RuntimeMode.HYBRID)
        self.assertEqual(ExecutionKind.CONTROL_QUERY, decision.execution_kind)
        self.assertIsNone(decision.routing)

    def test_two_distinct_stages_are_phased_even_with_explicit_skill(self) -> None:
        directive = resolve_directive(DirectiveInput("使用 api-designer", ("skill:local/api-designer",), "use"))
        decision = decide_request(
            GoalRelation.NONE, TaskSignals(intent_count=1, domain_count=1, distinct_stages=2),
            directive, RuntimeMode.HYBRID,
        )
        self.assertEqual(RoutingEnvelope.PHASED, decision.routing.envelope)
        self.assertEqual(SelectionMode.EXPLICIT_LOCKED, decision.routing.skill_policy)

    def test_active_goal_side_question_is_detached_read_only_not_managed_goal(self) -> None:
        decision = decide_request(GoalRelation.SIDE_QUESTION, TaskSignals.small(), UserDirective.auto(), RuntimeMode.HYBRID)
        self.assertNotEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)

    def test_progress_in_active_goal_uses_managed_goal(self) -> None:
        decision = decide_request(GoalRelation.PROGRESS, TaskSignals.small(), UserDirective.auto(), RuntimeMode.HYBRID)
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)

    def test_explicit_phased_mode_overrides_small_size_classifier(self) -> None:
        directive = replace(UserDirective.auto(), requested_work_mode=RoutingEnvelope.PHASED)
        decision = decide_request(GoalRelation.NONE, TaskSignals.small(), directive, RuntimeMode.HYBRID)
        self.assertEqual(RoutingEnvelope.PHASED, decision.routing.envelope)

    def test_single_mode_inside_native_goal_keeps_outer_goal_and_scopes_current_item(self) -> None:
        directive = replace(UserDirective.auto(), requested_work_mode=RoutingEnvelope.SINGLE)
        decision = decide_request(GoalRelation.PROGRESS, TaskSignals.large(), directive, RuntimeMode.HYBRID)
        self.assertEqual(RoutingEnvelope.MANAGED_GOAL, decision.routing.envelope)
        self.assertEqual(RoutingEnvelope.SINGLE, decision.routing.work_item_envelope_override)
```

- [ ] **Step 2: Run tests and verify the new routing package is absent**

Run: `python -m unittest packages/router-core/tests/routing/test_profiler.py -v`

Expected: FAIL with `ModuleNotFoundError: ...routing.profiler`。

- [ ] **Step 3: Implement the typed contracts and deterministic classifier**

```python
# packages/router-core/src/workflow_skill_router/routing/profiler.py
def decide_request(goal_relation, signals, directive, runtime_mode):
    if goal_relation is GoalRelation.STATUS:
        return RequestDecision(goal_relation, ExecutionKind.CONTROL_QUERY, None)
    if goal_relation in (GoalRelation.PROGRESS, GoalRelation.STEER):
        envelope = RoutingEnvelope.MANAGED_GOAL
        work_item_override = directive.requested_work_mode
    elif directive.requested_work_mode is not None:
        envelope = directive.requested_work_mode
        work_item_override = None
    elif signals.milestone_count > 1 or signals.resumable or signals.cross_repo or signals.dependency_dag:
        envelope = RoutingEnvelope.MANAGED_GOAL
        work_item_override = None
    elif signals.distinct_stages > 1 or signals.domain_count > 1 or signals.dependency_edges > 0:
        envelope = RoutingEnvelope.PHASED
        work_item_override = None
    else:
        envelope = RoutingEnvelope.SINGLE
        work_item_override = None
    routing = RoutingProfile(
        envelope=envelope,
        work_item_envelope_override=work_item_override,
        skill_policy=SelectionMode.EXPLICIT_LOCKED if directive.explicit_skills else SelectionMode.AUTO,
        risk=signals.risk,
        runtime_mode=runtime_mode,
    )
    return RequestDecision(goal_relation, ExecutionKind.ROUTED_WORK, routing)
```

`models.py` must use exact serialized values from the spec: `single | phased | managed-goal`、`control-query | routed-work`、`none | progress | steer | status | side-question | unrelated`、`auto | explicit-locked`、`skill-only | hybrid`。`resolve_directive()` separately parses explicit work-mode language and SKILL language；it maps `use -> preferred_primary + ask`、`only -> allowed_set + forbid`、`all -> required_all + ask`，while multiple IDs with no semantic hint raises `DirectiveAmbiguityError` instead of guessing。A user work mode overrides only the size classifier；inside an active native Goal, Single/Phased scopes the current Work Item while the outer Goal Binding remains managed-goal。

- [ ] **Step 4: Run focused and full existing tests, then commit**

Run: `python -m unittest packages/router-core/tests/routing/test_profiler.py -v`

Expected: all profiler tests PASS。

Run: `python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v`

Expected: plan 01 golden／capability tests and new routing tests all PASS。

```bash
git add packages/router-core/src/workflow_skill_router/routing packages/router-core/tests/routing/test_profiler.py
git commit -m "feat(core): classify routed work envelopes"
```

### Task 2: Enforce semantic scope anchors, explicit lock inheritance, dispositions, and coverage

**Files:**
- Modify: `packages/router-core/src/workflow_skill_router/routing/models.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/scope.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/coverage.py`
- Create: `packages/router-core/tests/routing/test_explicit_lock.py`

**Interfaces:**
- Consumes: normalized `UserDirective` and `RoutingEnvelope` from Task 1。
- Produces: `ScopeKind`、`ScopeAnchor`、`ScopeIndex.is_same_or_descendant(*, candidate_id: str, ancestor_id: str) -> bool`、`SkillConstraint`、`SkillSelectionPolicy`、`SkillDisposition`、`ExplicitSkillDisposition`、`CoverageStatus`、`ExplicitSkillCoverage`；`create_scope_anchor()`、`descendant_anchor()`、`inherit_explicit_policy()`、`evaluate_explicit_coverage(policy, dispositions, activation_refs, primary_route_refs, user_waivers) -> tuple[ExplicitSkillCoverage, ...]`。The named argument order is canonical everywhere；unknown IDs or cycles return `False` and cannot be treated as descendants。

- [ ] **Step 1: Write failing tests for lock inheritance and scope-level coverage**

```python
# packages/router-core/tests/routing/test_explicit_lock.py
class ExplicitLockTests(unittest.TestCase):
    def test_replacement_phase_keeps_semantic_anchor_and_lock(self) -> None:
        workflow = create_scope_anchor(ScopeKind.WORKFLOW, "workflow-1", None, "objective-a", 1)
        phase = descendant_anchor(workflow, ScopeKind.PHASE, "phase-1", "api-contract", 1)
        replacement = replacement_anchor(phase, replacement_aggregate_id="phase-2", created_revision=2)
        self.assertEqual(phase.scope_anchor_id, replacement.scope_anchor_id)
        self.assertEqual(("skill:local/api-designer",), inherit_explicit_policy(POLICY, replacement, SCOPE_INDEX).explicit_skill_ids)

    def test_same_semantic_siblings_in_same_or_different_workflows_never_collide(self) -> None:
        first_root = create_scope_anchor(ScopeKind.WORKFLOW, "workflow-1", None, "objective-a", 1)
        second_root = create_scope_anchor(ScopeKind.WORKFLOW, "workflow-2", None, "objective-a", 1)
        first = descendant_anchor(first_root, ScopeKind.PHASE, "phase-1", "api-contract", 1)
        sibling = descendant_anchor(first_root, ScopeKind.PHASE, "phase-2", "api-contract", 1)
        other = descendant_anchor(second_root, ScopeKind.PHASE, "phase-1", "api-contract", 1)
        self.assertEqual(3, len({first.scope_anchor_id, sibling.scope_anchor_id, other.scope_anchor_id}))

    def test_required_all_cannot_pass_with_allowed_not_selected(self) -> None:
        coverage = evaluate_explicit_coverage(REQUIRED_ALL_POLICY, (
            disposition("skill:a", SkillDisposition.ACTIVE_REQUIRED),
            disposition("skill:b", SkillDisposition.ALLOWED_NOT_SELECTED),
        ), {"skill:a": ("activation-1",)}, {}, {})
        self.assertEqual(CoverageStatus.SATISFIED, coverage[0].status)
        self.assertEqual(CoverageStatus.UNCOVERED, coverage[1].status)

    def test_preferred_primary_requires_one_primary_route(self) -> None:
        coverage = evaluate_explicit_coverage(PREFERRED_POLICY, (disposition("skill:a", SkillDisposition.NOT_APPLICABLE),), {}, {}, {})
        self.assertEqual(CoverageStatus.UNCOVERED, coverage[0].status)
```

- [ ] **Step 2: Run tests and verify scope／coverage modules are missing**

Run: `python -m unittest packages/router-core/tests/routing/test_explicit_lock.py -v`

Expected: FAIL with missing `routing.scope` or `routing.coverage`。

- [ ] **Step 3: Implement stable semantic anchor identity and deny-by-default inheritance**

```python
# packages/router-core/src/workflow_skill_router/routing/scope.py
def create_scope_anchor(kind, aggregate_id, parent_scope_anchor_id, semantic_scope_digest,
                        created_revision, lineage_root_id=None, stable_scope_key=None):
    lineage_root_id = lineage_root_id or aggregate_id
    stable_scope_key = stable_scope_key or aggregate_id
    identity = canonical_json({
        "anchor_kind": kind.value,
        "lineage_root_id": lineage_root_id,
        "stable_scope_key": stable_scope_key,
        "parent_scope_anchor_id": parent_scope_anchor_id,
        "semantic_scope_digest": semantic_scope_digest,
    })
    anchor_id = "scope:sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return ScopeAnchor(anchor_id, kind, aggregate_id, parent_scope_anchor_id, semantic_scope_digest,
                       lineage_root_id, stable_scope_key, created_revision)


def descendant_anchor(parent, kind, aggregate_id, semantic_scope_digest, created_revision):
    return create_scope_anchor(
        kind, aggregate_id, parent.scope_anchor_id, semantic_scope_digest, created_revision,
        lineage_root_id=parent.lineage_root_id, stable_scope_key=aggregate_id,
    )


def replacement_anchor(previous, replacement_aggregate_id, created_revision):
    return create_scope_anchor(
        previous.kind, replacement_aggregate_id, previous.parent_scope_anchor_id,
        previous.semantic_scope_digest, created_revision,
        lineage_root_id=previous.lineage_root_id,
        stable_scope_key=previous.stable_scope_key,
    )


def inherit_explicit_policy(policy, anchor, scope_index):
    if policy.mode is SelectionMode.AUTO:
        return policy
    if not scope_index.is_same_or_descendant(
        candidate_id=anchor.scope_anchor_id, ancestor_id=policy.scope_anchor_id,
    ):
        raise ScopePolicyError("目標 scope 不在 explicit lock 的 descendant 範圍")
    return policy
```

`ScopeAnchor` stores both immutable `lineage_root_id` and `stable_scope_key`。Normal creation derives a fresh stable key from the server-owned aggregate ID；only `replacement_anchor(previous, ...)` may carry an existing key, after verifying same parent/kind/semantic scope and lineage。Thus equivalent text does not alias siblings or workflows, while a real replacement preserves policy identity。`SkillSelectionPolicy` contains the exact spec fields: mode、explicit skills／semantics、support policy、approved/rejected references、consent scope、lock scope、scope anchor、plan revision。`coverage.py` must reject `required_all + allowed-not-selected`、require activation evidence for every required skill、require at least one primary route for `preferred_primary`, and ensure every non-forced activation under `allowed_set` is either in-set or backed by valid consent。All-not-applicable never auto-passes。

- [ ] **Step 4: Run coverage tests and commit**

Run: `python -m unittest packages/router-core/tests/routing/test_explicit_lock.py -v`

Expected: all explicit lock and coverage tests PASS。

```bash
git add packages/router-core/src/workflow_skill_router/routing/models.py packages/router-core/src/workflow_skill_router/routing/scope.py packages/router-core/src/workflow_skill_router/routing/coverage.py packages/router-core/tests/routing/test_explicit_lock.py
git commit -m "feat(core): enforce explicit skill scope coverage"
```

### Task 3: Implement phase-scoped support proposal, grant, rejection, and invalidation

**Files:**
- Modify: `packages/router-core/src/workflow_skill_router/routing/models.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/consent.py`
- Create: `packages/router-core/tests/routing/test_consent.py`

**Interfaces:**
- Consumes: `ScopeAnchor`、`SkillSelectionPolicy` from Task 2 and capability fingerprint／kind from plan 01。
- Produces: `SupportProposal`、`ConsentGrant`、`ConsentRejection`、`ConsentDecision`；`material_context_fingerprint()`、`propose_support()`、`match_grant()`、`may_reask_after_rejection()`、`validate_support_selection()`。

- [ ] **Step 1: Write failing tests for approval scope, rejection memory, and material changes**

```python
# packages/router-core/tests/routing/test_consent.py
class ConsentTests(unittest.TestCase):
    def test_proposal_is_limited_to_three_distinct_support_skills(self) -> None:
        with self.assertRaisesRegex(ConsentPolicyError, "最多三個"):
            propose_support(PHASE_ANCHOR, (proposal("a"), proposal("b"), proposal("c"), proposal("d")))

    def test_phase_grant_does_not_apply_to_sibling_phase(self) -> None:
        grant = approved_grant(scope_anchor_id="scope:phase-a", context_fingerprint="ctx-1")
        self.assertTrue(match_grant(grant, request_for("scope:phase-a", "ctx-1"), SCOPE_INDEX))
        self.assertFalse(match_grant(grant, request_for("scope:phase-b", "ctx-1"), SCOPE_INDEX))

    def test_explicit_workflow_grant_applies_to_descendant_phase(self) -> None:
        grant = approved_grant(scope=ScopeKind.WORKFLOW, scope_anchor_id="scope:workflow", context_fingerprint="ctx-1")
        self.assertTrue(match_grant(grant, request_for("scope:phase-a", "ctx-1"), SCOPE_INDEX))

    def test_same_rejection_cannot_be_reasked_after_phase_id_replacement(self) -> None:
        rejection = rejected(scope_anchor_id="scope:semantic-api", phase_id="phase-old", context_fingerprint="ctx-1")
        request = request_for("scope:semantic-api", "ctx-1", phase_id="phase-new")
        self.assertFalse(may_reask_after_rejection(rejection, request))

    def test_material_context_change_allows_explained_reproposal(self) -> None:
        self.assertTrue(may_reask_after_rejection(rejected(context_fingerprint="ctx-old"), request_for(context_fingerprint="ctx-new")))
```

- [ ] **Step 2: Run tests and verify consent implementation is missing**

Run: `python -m unittest packages/router-core/tests/routing/test_consent.py -v`

Expected: FAIL with `ModuleNotFoundError: ...routing.consent`。

- [ ] **Step 3: Implement material matching without treating numeric reordering as consent**

```python
# packages/router-core/src/workflow_skill_router/routing/consent.py
def material_context_fingerprint(capability_fingerprint, purpose_class, scope_anchor_id, goal_revision, semantic_context_digest):
    document = {
        "capability_fingerprint": capability_fingerprint,
        "purpose_class": purpose_class,
        "scope_anchor_id": scope_anchor_id,
        "goal_revision": goal_revision,
        "semantic_context_digest": semantic_context_digest,
    }
    return "sha256:" + hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def match_grant(grant, request, scope_index, now=None):
    current = now or datetime.now(timezone.utc)
    return (
        grant.capability_id == request.capability_id
        and grant.capability_fingerprint == request.capability_fingerprint
        and grant.purpose == request.purpose
        and scope_index.is_same_or_descendant(
            candidate_id=request.scope_anchor_id, ancestor_id=grant.scope_anchor_id,
        )
        and grant.context_fingerprint == request.context_fingerprint
        and grant.expires_at > current
    )


def may_reask_after_rejection(rejection, request):
    same_key = (
        rejection.capability_id == request.capability_id
        and rejection.purpose == request.purpose
        and rejection.scope_anchor_id == request.scope_anchor_id
    )
    return not same_key or rejection.context_fingerprint != request.context_fingerprint
```

`ConsentGrant`／`ConsentRejection` fields must exactly include capability、purpose／role、scope／anchor、work item、phase、Goal binding／revision、plan revision、context fingerprint、actor and timestamps from §9.4。Plan revision is audited but a numeric revision-only reorder does not change `material_context_fingerprint`。`support_policy=forbid` returns a forbidden decision without proposal；a rejected same-key proposal returns an existing-rejection decision and never asks again。

- [ ] **Step 4: Run consent tests and commit**

Run: `python -m unittest packages/router-core/tests/routing/test_consent.py -v`

Expected: all consent tests PASS。

```bash
git add packages/router-core/src/workflow_skill_router/routing/models.py packages/router-core/src/workflow_skill_router/routing/consent.py packages/router-core/tests/routing/test_consent.py
git commit -m "feat(core): validate scoped support consent"
```

### Task 4: Derive selection authority server-side and enforce manifest requirement trust

**Files:**
- Create: `packages/router-core/src/workflow_skill_router/routing/authority.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/trust.py`
- Create: `packages/router-core/tests/routing/test_authority_and_trust.py`

**Interfaces:**
- Consumes: capability `Requirement`／snapshot and policy／consent contracts from Tasks 2–3。
- Produces: `SelectionOrigin`、`SelectionAuthority`、`RuntimePolicySnapshot`、`VerifiedDirectiveEvent`、`RequirementTrustPolicy`、`RequirementTrustDecision`；`AuthorityResolver.resolve()`；`assess_requirement()`。

- [ ] **Step 1: Write failing provenance and privilege-boundary tests**

```python
# packages/router-core/tests/routing/test_authority_and_trust.py
class AuthorityAndTrustTests(unittest.TestCase):
    def test_client_cannot_self_declare_system_required(self) -> None:
        result = RESOLVER.resolve(
            SelectionOrigin.SYSTEM_REQUIRED, "missing",
            capability_id="skill:x", purpose="implement", scope_anchor_id="phase-1",
        )
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, result.selection_origin)
        self.assertTrue(result.requires_consent)

    def test_verified_user_directive_produces_user_explicit_origin(self) -> None:
        result = RESOLVER.resolve(
            SelectionOrigin.USER_EXPLICIT, DIRECTIVE.event_id,
            capability_id="skill:x", purpose="implement", scope_anchor_id="phase-1",
            directive_event=DIRECTIVE,
        )
        self.assertEqual(SelectionOrigin.USER_EXPLICIT, result.selection_origin)
        self.assertFalse(result.requires_consent)

    def test_verified_directive_cannot_be_replayed_for_another_capability_or_scope(self) -> None:
        replayed = RESOLVER.resolve(
            SelectionOrigin.USER_EXPLICIT, DIRECTIVE.event_id,
            capability_id="skill:y", purpose="implement", scope_anchor_id="phase-2",
            directive_event=DIRECTIVE,
        )
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, replayed.selection_origin)
        self.assertTrue(replayed.requires_consent)

    def test_workflow_directive_inherits_only_to_validated_descendant_phase(self) -> None:
        inherited = RESOLVER.resolve(
            SelectionOrigin.USER_EXPLICIT, WORKFLOW_DIRECTIVE_X.event_id,
            capability_id="skill:x", purpose="implement", scope_anchor_id="phase-child-1",
            directive_event=WORKFLOW_DIRECTIVE_X,
        )
        sibling = RESOLVER.resolve(
            SelectionOrigin.USER_EXPLICIT, WORKFLOW_DIRECTIVE_X.event_id,
            capability_id="skill:x", purpose="implement", scope_anchor_id="phase-other-workflow",
            directive_event=WORKFLOW_DIRECTIVE_X,
        )
        self.assertEqual(SelectionOrigin.USER_EXPLICIT, inherited.selection_origin)
        self.assertEqual(SelectionOrigin.ROUTER_RECOMMENDED, sibling.selection_origin)

    def test_skill_requirement_never_bypasses_explicit_lock(self) -> None:
        decision = assess_requirement(skill_requirement("skill:y"), parent_skill="skill:x", snapshot=SNAPSHOT, policy=TRUST_POLICY)
        self.assertFalse(decision.trusted_as_base_requirement)
        self.assertTrue(decision.requires_support_consent)

    def test_remote_plugin_requirement_needs_capability_consent_and_runtime_approval(self) -> None:
        decision = assess_requirement(remote_plugin_requirement(), "skill:x", SNAPSHOT, TRUST_POLICY)
        self.assertTrue(decision.requires_capability_consent)
        self.assertTrue(decision.requires_runtime_approval)
```

- [ ] **Step 2: Run tests and verify authority／trust modules are absent**

Run: `python -m unittest packages/router-core/tests/routing/test_authority_and_trust.py -v`

Expected: FAIL with missing routing modules。

- [ ] **Step 3: Implement downgrade-on-unverifiable authority and deny-by-default requirements**

```python
# packages/router-core/src/workflow_skill_router/routing/authority.py
class AuthorityResolver:
    def __init__(self, runtime_policy_snapshot, directive_events, authenticated_context, scope_index):
        self._policy = runtime_policy_snapshot
        self._directives = {item.event_id: item for item in directive_events}
        self._context = authenticated_context
        self._scopes = scope_index

    def resolve(
        self, requested_origin, authority_ref, *, capability_id, purpose,
        scope_anchor_id, directive_event=None,
    ):
        if requested_origin in FORCED_ORIGINS:
            rule = self._policy.rules.get(authority_ref)
            if rule and rule.origin is requested_origin and self._scopes.is_same_or_descendant(
                candidate_id=scope_anchor_id, ancestor_id=rule.scope_anchor_id,
            ) and rule.matches(
                capability_id=capability_id,
                purpose=purpose,
                policy_snapshot_id=self._policy.snapshot_id,
                actor=self._context.actor,
                session_id=self._context.session_id,
            ):
                return SelectionAuthority(requested_origin, authority_ref, self._policy.snapshot_id, self._policy.policy_digest, "router-core", False)
        if requested_origin is SelectionOrigin.USER_EXPLICIT:
            verified = self._directives.get(authority_ref)
            if verified and verified == directive_event and self._scopes.is_same_or_descendant(
                candidate_id=scope_anchor_id, ancestor_id=verified.scope_anchor_id,
            ) and verified.binds(
                capability_id=capability_id,
                purpose=purpose,
                policy_snapshot_id=self._policy.snapshot_id,
                actor=self._context.actor,
                session_id=self._context.session_id,
            ):
                return SelectionAuthority(requested_origin, authority_ref, self._policy.snapshot_id, self._policy.policy_digest, "router-core", False)
        return SelectionAuthority(SelectionOrigin.ROUTER_RECOMMENDED, "router-derived", self._policy.snapshot_id, self._policy.policy_digest, "router-core", True)
```

Policy rules and verified directive events are capability/purpose/scope records, not reusable origin labels。`ScopeIndex` is built from validated `ScopeAnchor` ancestry and permits only same-or-descendant inheritance：a workflow/work-item directive may govern its own phase descendants, but never a sibling workflow, unrelated work item or ancestor。Unknown/cyclic ancestry fails closed。A mismatch in capability ID、purpose、scope ancestry、policy snapshot、authenticated actor/session or directive digest downgrades to `router-recommended` and records `authority-binding-mismatch`；it never preserves the requested privileged origin。`assess_requirement()` only trusts versioned base-runtime IDs or allowlisted non-SKILL kinds with matching provider provenance、purpose、fingerprint and side-effect class。Every `kind=skill` returns `requires_support_consent=True`；untrusted requirement yields degraded／blocked, never auto-activation。Remote／privileged returns both capability consent and runtime approval requirements。Installation、authentication、new connector are always separate authorization outcomes。

- [ ] **Step 4: Run authority/trust tests and commit**

Run: `python -m unittest packages/router-core/tests/routing/test_authority_and_trust.py -v`

Expected: all authority and manifest trust tests PASS。

```bash
git add packages/router-core/src/workflow_skill_router/routing/authority.py packages/router-core/src/workflow_skill_router/routing/trust.py packages/router-core/tests/routing/test_authority_and_trust.py
git commit -m "feat(core): verify selection authority and requirements"
```

### Task 5: Validate routes, issue non-escalating leases, and prove small／medium explicit-SKILL behavior

**Files:**
- Modify: `packages/router-core/src/workflow_skill_router/routing/models.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/validator.py`
- Create: `packages/router-core/src/workflow_skill_router/routing/leases.py`
- Create: `packages/router-core/tests/routing/test_route_validator.py`
- Create: `packages/router-core/tests/routing/test_explicit_skill_scenarios.py`

**Interfaces:**
- Consumes: plan 01 `CapabilitySnapshot`; Tasks 1–4 envelope、policy、consent、authority、trust and coverage。
- Produces: `CapabilitySelection`、`Route`、`ActivationBindingKind`、`LeaseActivationBinding`、`LeaseCapability`、`ExecutionLease`、server-owned `InvocationContext`、`LeaseConsumptionRequest`、`LeaseConsumptionReceipt`、`LeaseConsumptionPort`、`InvocationDecision`、`RouteValidationRequest`、`ValidationContext`、`RouteViolation`、`RouteValidationResult`；`RouteValidator.validate(request, snapshot, policy, context) -> RouteValidationResult`；`issue_execution_lease()`；`validate_invocation()`。`Route`／`ExecutionLease` signatures must remain the shared signatures referenced by plans 03/04。

The shared contract in `routing/models.py` is exact:

```python
@dataclass(frozen=True, slots=True)
class CapabilitySelection:
    capability_id: str; capability_fingerprint: str; selection_origin: SelectionOrigin
    authority_ref: str; policy_digest: str; purpose: str; consent_grant_ref: str | None

@dataclass(frozen=True, slots=True)
class Route:
    route_id: str; workflow_run_id: str; work_item_id: str; phase_id: str
    envelope: RoutingEnvelope; capability_snapshot_id: str
    primary_selection: CapabilitySelection; support_selections: tuple[CapabilitySelection, ...]
    skill_policy_revision: int; explicit_skill_dispositions: tuple[ExplicitSkillDisposition, ...]
    explicit_skill_coverage_ref: str | None; consent_grant_refs: tuple[str, ...]
    risk: RiskLevel; context_cost: int; validation_status: str
    validation_reasons: tuple[str, ...]; created_at: str

@dataclass(frozen=True, slots=True)
class LeaseActivationBinding:
    kind: str  # instruction-content | tool-schema | runtime-contract
    trusted_digest: str

@dataclass(frozen=True, slots=True)
class LeaseCapability:
    capability_id: str; capability_kind: CapabilityKind
    capability_fingerprint: str; selection_origin: SelectionOrigin
    authority_ref: str; policy_digest: str; purpose: str; consent_grant_ref: str | None
    activation_binding: LeaseActivationBinding

@dataclass(frozen=True, slots=True)
class ExecutionLease:
    lease_id: str; workflow_run_id: str; phase_id: str; scope_anchor_id: str
    route_id: str; capability_snapshot_id: str; policy_revision: int; state_version: int
    runtime_policy_snapshot_id: str; action_digest: str
    runtime_approval_ref: str | None; runtime_approval_scope_digest: str | None
    content_preflight_policy_digest: str
    allowed_capabilities: tuple[LeaseCapability, ...]; issued_at: str; expires_at: str
    max_activations: int; activation_mode: str  # always 1 / single-use-preflight

@dataclass(frozen=True, slots=True)
class InvocationContext:
    scope_anchor_id: str; purpose: str; actor: str; session_id: str
    runtime_policy_snapshot_id: str; context_digest: str

@dataclass(frozen=True, slots=True)
class LeaseConsumptionRequest:
    lease_id: str; capability_id: str; capability_fingerprint: str
    scope_anchor_id: str; purpose: str; invocation_context_digest: str
    activation_binding_kind: str; observed_binding_digest: str
    action_digest: str; runtime_approval_ref: str | None
    runtime_approval_scope_digest: str | None; state_version: int; invocation_nonce: str

@dataclass(frozen=True, slots=True)
class LeaseConsumptionReceipt:
    lease_id: str; invocation_digest: str; reservation_digest: str
    consumption_version: int; consumed_at: str
```

`RouteValidationRequest` must include the canonical `action_digest` and immutable scope/purpose；R2/R3 also references an opaque runtime approval。The validator resolves that approval server-side and `issue_execution_lease()` copies its verified ref/scope digest plus the trusted policy snapshot。Every immediate activation gets its own lease with `max_activations=1` and `activation_mode="single-use-preflight"`。The selected capability carries a tagged binding：SKILL uses `instruction-content` plus non-unknown trusted installer digest；MCP tool uses `tool-schema` plus verified handshake schema digest；plugin/app/host tool uses `runtime-contract` plus verified host contract digest。A kind/binding mismatch is invalid；non-SKILL capability never invents or opens a SKILL body。Missing relevant preflight support returns `content-preflight-unavailable` or `runtime-contract-preflight-unavailable` (or explicitly disclosed skill-only fallback outside the hybrid lease contract)。`LeaseConsumptionPort.compare_and_consume(request, expected_consumption_version=0) -> LeaseConsumptionReceipt` is a required fail-closed protocol and both DTOs above are exact：the request binds lease、capability/fingerprint、server-derived scope/purpose/context digest、tagged observed binding digest、action digest、verified runtime approval scope、state version and invocation nonce；the receipt is a pre-host reservation, not a host activation receipt。Plan 02 uses an atomic in-memory fake for domain tests；Plan 03 supplies the SQLite transaction that reserves one activation and stores its typed binding。

- [ ] **Step 1: Write failing hard-policy and scenario-matrix tests**

```python
# packages/router-core/tests/routing/test_explicit_skill_scenarios.py
class ExplicitSkillScenarioTests(unittest.TestCase):
    def test_small_explicit_skill_routes_only_that_skill_after_support_rejection(self) -> None:
        result = validate_small_explicit(primary="skill:x", proposed_support="skill:y", rejection=REJECTION_Y)
        self.assertEqual(RoutingEnvelope.SINGLE, result.route.envelope)
        self.assertEqual("skill:x", result.route.primary_selection.capability_id)
        self.assertEqual((), result.route.support_selections)
        self.assertEqual(OutcomeMode.LIMITED, result.outcome_mode)

    def test_small_only_x_forbids_support_proposal_and_activation(self) -> None:
        result = validate_small_only("skill:x", attempted_support="skill:y")
        self.assertFalse(result.valid)
        self.assertIn("support-forbidden", {item.code for item in result.violations})

    def test_medium_explicit_lock_is_checked_in_every_phase(self) -> None:
        phase_one, phase_two = validate_medium_explicit(PHASE_PLAN, explicit_skill="skill:x")
        self.assertEqual(RoutingEnvelope.PHASED, phase_one.route.envelope)
        self.assertEqual(RoutingEnvelope.PHASED, phase_two.route.envelope)
        self.assertTrue(all(item.skill_id == "skill:x" for item in phase_one.route.explicit_skill_dispositions))
        self.assertTrue(all(item.skill_id == "skill:x" for item in phase_two.route.explicit_skill_dispositions))

    def test_phase_one_support_grant_cannot_be_reused_in_phase_two(self) -> None:
        result = validate_phase_two_with_phase_one_grant()
        self.assertFalse(result.valid)
        self.assertIn("support-consent-missing", {item.code for item in result.violations})

    def test_rejected_support_keeps_original_exit_gate_and_honestly_blocks(self) -> None:
        result = replan_after_support_rejection(EXIT_GATE_REQUIRES_Y)
        self.assertEqual(EXIT_GATE_REQUIRES_Y, result.exit_gate)
        self.assertEqual(OutcomeMode.BLOCKED, result.outcome_mode)
        self.assertNotEqual(CoverageStatus.SATISFIED, result.coverage.status)
```

```python
# packages/router-core/tests/routing/test_route_validator.py
class RouteValidatorTests(unittest.TestCase):
    def test_unavailable_capability_never_receives_lease(self) -> None:
        result = VALIDATOR.validate(request_for("skill:missing"), SNAPSHOT, AUTO_POLICY, CONTEXT)
        self.assertFalse(result.valid)
        self.assertIsNone(result.lease)

    def test_r3_requires_fresh_snapshot_runtime_approval_and_action_digest(self) -> None:
        result = VALIDATOR.validate(R3_REQUEST, STALE_SNAPSHOT, AUTO_POLICY, CONTEXT_WITHOUT_APPROVAL)
        self.assertEqual({"snapshot-stale", "runtime-approval-required", "action-digest-required"}, {item.code for item in result.violations})

    def test_expired_lease_cannot_authorize_new_invocation(self) -> None:
        decision = validate_invocation(
            EXPIRED_LEASE, "skill:x", "fingerprint-x", ACTION_DIGEST,
            RUNTIME_APPROVAL, INSTALLER_CONTENT_DIGEST, STATE_VERSION, NOW,
            invocation_context=SERVER_INVOCATION_CONTEXT,
            invocation_nonce="invocation-expired", consumption_port=self.consumptions,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("lease-expired", decision.reason)

    def test_invocation_binds_action_approval_and_content_then_consumes_once(self) -> None:
        first = validate_invocation(
            VALID_LEASE, "skill:x", "fingerprint-x", ACTION_DIGEST,
            RUNTIME_APPROVAL, INSTALLER_CONTENT_DIGEST, STATE_VERSION, NOW,
            invocation_context=SERVER_INVOCATION_CONTEXT,
            invocation_nonce="invocation-1", consumption_port=self.consumptions,
        )
        second = validate_invocation(
            VALID_LEASE, "skill:x", "fingerprint-x", ACTION_DIGEST,
            RUNTIME_APPROVAL, INSTALLER_CONTENT_DIGEST, STATE_VERSION, NOW,
            invocation_context=SERVER_INVOCATION_CONTEXT,
            invocation_nonce="invocation-2", consumption_port=self.consumptions,
        )
        self.assertTrue(first.allowed)
        self.assertEqual("lease-consumed", second.reason)

    def test_concurrent_lease_consumption_allows_exactly_one_invocation(self) -> None:
        decisions = race_two_valid_invocations(VALID_LEASE, self.consumptions)
        self.assertEqual(1, sum(item.allowed for item in decisions))
        self.assertEqual(1, sum(item.reason == "lease-consumed" for item in decisions))

    def test_lease_cannot_replay_across_purpose_or_scope(self) -> None:
        for context in (
            replace(SERVER_INVOCATION_CONTEXT, purpose="publish"),
            replace(SERVER_INVOCATION_CONTEXT, scope_anchor_id="phase-other"),
        ):
            with self.subTest(context=context):
                decision = validate_invocation(
                    VALID_LEASE, "skill:x", "fingerprint-x", ACTION_DIGEST,
                    RUNTIME_APPROVAL, INSTALLER_CONTENT_DIGEST, STATE_VERSION, NOW,
                    invocation_context=context, invocation_nonce="replay",
                    consumption_port=self.consumptions,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual("invocation-context-mismatch", decision.reason)

    def test_hybrid_lease_is_single_use_and_requires_bound_content_preflight(self) -> None:
        result = VALIDATOR.validate(VALID_REQUEST, SNAPSHOT, AUTO_POLICY, CONTEXT_WITH_BOUND_CONTENT)
        self.assertTrue(result.valid)
        self.assertEqual((1, "single-use-preflight"), (result.lease.max_activations, result.lease.activation_mode))
        self.assertEqual("instruction-content", result.lease.allowed_capabilities[0].activation_binding.kind)
        missing = VALIDATOR.validate(VALID_REQUEST, SNAPSHOT, AUTO_POLICY, CONTEXT_WITHOUT_BOUND_CONTENT)
        self.assertIn("content-preflight-unavailable", {item.code for item in missing.violations})

    def test_non_skill_lease_uses_verified_runtime_binding_without_opening_skill_body(self) -> None:
        result = VALIDATOR.validate(MCP_REQUEST, SNAPSHOT, AUTO_POLICY, CONTEXT_WITH_TOOL_SCHEMA_PREFLIGHT)
        binding = result.lease.allowed_capabilities[0].activation_binding
        self.assertEqual("tool-schema", binding.kind)
        self.assertEqual(MCP_SCHEMA_DIGEST, binding.trusted_digest)
        self.assertEqual([], CONTEXT_WITH_TOOL_SCHEMA_PREFLIGHT.instruction_body_opens)
```

- [ ] **Step 2: Run route and matrix tests and verify validator is absent**

Run: `python -m unittest packages/router-core/tests/routing/test_route_validator.py packages/router-core/tests/routing/test_explicit_skill_scenarios.py -v`

Expected: FAIL with missing `routing.validator`／`routing.leases`。

- [ ] **Step 3: Implement ordered validation and lease issuance**

```python
# packages/router-core/src/workflow_skill_router/routing/validator.py
class RouteValidator:
    def validate(self, request, snapshot, policy, context):
        violations = []
        capabilities = {item.canonical_id: item for item in snapshot.capabilities}
        for selection in (request.primary_selection, *request.support_selections):
            capability = capabilities.get(selection.capability_id)
            if capability is None:
                violations.append(RouteViolation("capability-not-in-snapshot", selection.capability_id))
                continue
            availability = derive_availability(capability, request.risk, context.now)
            if availability.primary not in context.allowed_availability:
                violations.append(RouteViolation("capability-unavailable", selection.capability_id))
            if capability.capability_fingerprint != selection.capability_fingerprint:
                violations.append(RouteViolation("capability-fingerprint-mismatch", selection.capability_id))
            violations.extend(validate_selection_authority(selection, context.authority_resolver))
            violations.extend(validate_selection_consent(selection, policy, context))
        violations.extend(validate_explicit_lock(request, policy, context))
        violations.extend(validate_risk_preflight(request, snapshot, context))
        if violations:
            return RouteValidationResult(False, tuple(violations), requires_runtime_approval(violations), None, request.outcome_mode)
        lease = issue_execution_lease(request, snapshot, policy, context)
        return RouteValidationResult(True, (), False, lease, request.outcome_mode)
```

Validation order is snapshot identity/availability/fingerprint、authority、explicit lock、consent、manifest trust、risk preflight、coverage、kind-specific preflight availability。`issue_execution_lease()` copies only validated fields, including scope/purpose、action digest、trusted runtime-policy snapshot、verified approval scope and tagged activation binding；it sets `max_activations=1` and `activation_mode="single-use-preflight"`, and expires at the earlier of 5 minutes/consent/approval。`InvocationContext` is reconstructed from authenticated session/current work projection, not client input；its canonical digest binds scope、purpose、actor、session and policy snapshot。`validate_invocation()` compares this context, capability kind/fingerprint、state version、action digest、runtime approval scope、binding tag and activation-time observed binding digest against the lease, then calls `LeaseConsumptionPort.compare_and_consume(..., expected_consumption_version=0)` as its final authorization step。The CAS loser returns `lease-consumed`；a mismatch fails before reservation。It cannot add capability or authorize a second activation。Skill-only fallback does not receive this hybrid execution lease。

- [ ] **Step 4: Complete the explicit scenario helpers as real end-to-end fixtures**

In `test_explicit_skill_scenarios.py`, construct real `CapabilitySnapshot`、`SkillSelectionPolicy`、`ScopeAnchor`、Grant／Rejection、RouteValidationRequest and `RouteValidator`; helper functions may assemble fixtures but must not stub `resolve_directive()`、`decide_request()`、`match_grant()`、`evaluate_explicit_coverage()` or `RouteValidator.validate()`。Cover this exact matrix:

| Scenario | Required assertion |
|---|---|
| Small auto | `single`、one minimal primary |
| Small explicit X | X is primary and activated |
| Small only X | Y is forbidden before proposal／activation |
| Small X-primary, Y rejected | continue X-only as limited, or blocked when gate cannot pass |
| Medium auto | `phased` and each phase can choose a different skill |
| Medium explicit X | every phase records X disposition; scope coverage spans workflow |
| Medium X-primary, Y phase grant | Y valid only in granted phase |
| Medium Y rejected | replacement phase keeps anchor; no repeat question; original mandatory gate remains |
| Managed Goal explicit X | Work Item／Phase split cannot bypass workflow／work-item lock |
| Managed Goal auto | each Work Item is reclassified as single/phased and has its own route |
| Managed Goal required_all X+Y | both required skills have dispositions/activation evidence in every affected scope or the candidate remains incomplete |

- [ ] **Step 5: Run the full routing suite, all core tests, and commit**

Run: `python -m unittest discover -s packages/router-core/tests/routing -p "test_*.py" -v`

Expected: all profiler、scope、coverage、consent、authority、trust、validator、lease and scenario matrix tests PASS。

Run: `python -m unittest discover -s packages/router-core/tests -p "test_*.py" -v`

Expected: all V1 compatibility and V2 core tests PASS。

Run: `python -m compileall -q packages/router-core/src packages/router-core/tests`

Expected: exit 0 and no output。

```bash
git add packages/router-core/src/workflow_skill_router/routing packages/router-core/tests/routing
git commit -m "feat(core): enforce routing consent and leases"
```

## Self-Review Record

- Spec coverage: Task 1 covers §8 RequestDecision、priority and Single／Phased／Managed Goal classification；Task 2 covers §8.7、§9.1、§9.5–§9.6；Task 3 covers §9.3–§9.7；Task 4 covers selection authority、Plugin/MCP support equivalence and manifest requirement trust；Task 5 covers §9.8 lease、R2/R3 checks and §26.1–§26.2 acceptance matrix。
- Small／medium explicit SKILL is not implicit: both have dedicated end-to-end fixtures, including only-X、preferred-X、required coverage、per-Phase disposition、phase-scoped support, rejection memory, limited result, honest block, and unchanged mandatory gate。
- Goal boundary is retained: progress／steer can select managed-goal, status short-circuits, side-question／unrelated do not mutate Goal semantics, and explicit policy remains an overlay rather than replacing Work Graph decomposition。
- 禁止樣板詞掃描：0 matches；every task has exact files, interfaces, a red command, implementation contract, a green command, and a commit boundary。
- Type consistency: `RoutingEnvelope.MANAGED_GOAL` serializes as `managed-goal`；`Route` and `ExecutionLease` are the single shared types consumed by plans 03/04；all capability references bind canonical ID plus fingerprint and snapshot ID。
- Security review: forced origins downgrade without trusted provenance；SKILL requirements never bypass consent；remote／privileged requirements retain runtime approval；grants cannot widen scope；rejections survive Phase ID replacement；leases cannot expand at invocation time。
