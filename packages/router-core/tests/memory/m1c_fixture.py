from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib
import json

from workflow_skill_router.memory import (
    CompletedWorkflowReader,
    MatcherSeed,
    MemoryPolicyRepository,
    MemoryRequestContext,
    MemoryStore,
    RememberWorkflowCommand,
    WorkflowMemoryService,
    build_route_observation,
    resolve_effective_policy,
)
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import RequestContext

from memory.workflow_fixture import WorkflowFixture, write_personal_memory_policy


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_feedback_policy(
    data_dir: Path,
    *,
    mode: str = "reviewed",
    retention_days: int = 90,
    max_observations: int = 1000,
    allow_free_text: bool = False,
) -> None:
    policy_dir = data_dir / "config"
    policy_dir.mkdir(parents=True, exist_ok=True)
    document: dict[str, object] = {
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "personal:m1c-test",
        "scope": "personal",
        "mode": mode,
        "storage": {
            "retention_days": retention_days,
            "max_observations": max_observations,
        },
    }
    if allow_free_text:
        document["privacy"] = {"free_text_feedback": "explicit-opt-in"}
        document["features"] = {
            "route_feedback": {"allow_free_text": True},
        }
    (policy_dir / "workflow-memory.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


class M1CHistoryFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.database = root / "router-v2.sqlite3"
        self.context = RequestContext("session-m1c", "developer", "runtime-policy-m1c")
        self.memory_context = MemoryRequestContext(
            self.context.session_id,
            self.context.actor,
            self.context.runtime_policy_snapshot_id,
        )
        self.workflow = WorkflowFixture(self.database, self.context)
        write_feedback_policy(root)
        self.service = WorkflowMemoryService(self.database, data_dir=root)

    def remember(self, *, key: str = "m1c-workflow"):
        plan = self.workflow.plan_single(key=key)
        self.workflow.complete(plan)
        result = self.service.remember_workflow(RememberWorkflowCommand(
            context=self.memory_context,
            workflow_run_id=plan.workflow_run_id,
            workspace_root=None,
            matcher_seed=MatcherSeed(("student api",), ("api",), (), "user-explicit"),
            target_profile_class="managed-personal",
            risk_class="r1",
            side_effect_outcome="none",
            one_shot="remember-once",
            idempotency_key=f"remember-{key}",
            correlation_id=f"correlation-remember-{key}",
        ))
        return plan, result

    def effective_policy(self):
        repository = MemoryPolicyRepository(self.root)
        return resolve_effective_policy(
            personal=repository.inspect_personal(), workspace=None
        )

    def insert_observations(
        self,
        *,
        count: int,
        dates: tuple[str, ...],
        route_digests: tuple[str, ...] | None = None,
        workspaces: tuple[str | None, ...] | None = None,
        route_sources: tuple[str, ...] | None = None,
        target_profile_class: str = "managed-personal",
    ) -> tuple[str, ...]:
        plan = self.workflow.plan_single(key="m1c-seed")
        self.workflow.complete(plan)
        completed = CompletedWorkflowReader(self.database).read(
            self.memory_context, plan.workflow_run_id
        )
        policy = self.effective_policy()
        seed = MatcherSeed(("student api",), ("api",), (), "user-explicit")
        ids: list[str] = []
        store = MemoryStore.open_if_enabled(self.root, policy)
        assert store is not None
        with store:
            for index in range(count):
                route_source = (
                    route_sources[index]
                    if route_sources is not None
                    else completed.route_source
                )
                workflow = replace(
                    completed,
                    workflow_run_id=f"workflow:m1c:{index}",
                    workflow_run_digest=digest({"workflow": index}),
                    workflow_fingerprint=digest({"fingerprint": index}),
                    workspace_identity_digest=(
                        workspaces[index]
                        if workspaces is not None
                        else completed.workspace_identity_digest
                    ),
                    route_source=route_source,
                )
                observation = build_route_observation(
                    workflow,
                    seed,
                    store.current_policy_snapshot,
                    target_profile_class=target_profile_class,
                    risk_class="r1",
                    side_effect_outcome="none",
                    observed_at=dates[index % len(dates)],
                )
                if route_digests is not None:
                    # Tests needing alternate routes use different matcher material,
                    # which deterministically changes the route signature.
                    observation = replace(
                        observation,
                        route_signature_digest=route_digests[index],
                    )
                    payload = observation.to_dict()
                    payload["observation_id"] = ""
                    payload["observation_digest"] = ""
                    # Do not persist a forged observation; route-diversity tests
                    # construct distinct matcher seeds instead.
                    raise AssertionError("route_digests override is unsupported")
                result = {
                    "status": "recorded",
                    "observation_id": observation.observation_id,
                    "observation_digest": observation.observation_digest,
                    "route_signature_digest": observation.route_signature_digest,
                    "policy_digest": policy.policy_digest,
                    "target_profile_class": target_profile_class,
                    "reason_codes": [],
                    "replayed": False,
                    "candidate_id": None,
                    "authority_mode": "router-local",
                }
                store.record_route_observation(
                    observation_document=observation.to_dict(),
                    result_document=result,
                    idempotency_key=f"synthetic-observation-{index}",
                    command_digest=digest({"synthetic": index}),
                )
                ids.append(observation.observation_id)
        return tuple(ids)
