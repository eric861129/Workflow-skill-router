from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.service_models import (
    EvaluateGate,
    PlanWork,
    RecordWorkEvent,
    RequestContext,
    RoutingContextInput,
)
from workflow_skill_router.workflow.local_observations import LocalProgressObservation


SINGLE_CHECK_ID = "router-local-single-completed"


def local_evidence_digest(check_ids: tuple[str, ...]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json({
        "evidence_class": "user-or-agent-reported-local",
        "persisted_check_ids": sorted(check_ids),
    }).encode("utf-8")).hexdigest()


def write_personal_memory_policy(data_dir: Path, mode: str) -> None:
    policy_dir = data_dir / "config"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "workflow-memory.json").write_text(json.dumps({
        "schema_id": "workflow-skill-router/memory-policy",
        "schema_version": "1.0.0",
        "artifact_kind": "memory-policy",
        "policy_id": "personal:test",
        "scope": "personal",
        "mode": mode,
    }), encoding="utf-8")


def write_phased_profile(data_dir: Path) -> None:
    profile_dir = data_dir / "profiles" / "personal"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "delivery.json").write_text(json.dumps({
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": "personal:delivery",
        "scope": "personal",
        "enabled": True,
        "rules": [{
            "rule_id": "delivery",
            "priority": 50,
            "match": {
                "objective_keywords": ["api"],
                "domains": ["api"],
                "tags": ["backend"],
                "work_modes": ["phased"],
            },
            "route": {
                "work_mode": "phased",
                "skill_tree": [
                    {
                        "phase_id": "design",
                        "primary_skill_id": "skill:api-designer",
                        "support_skill_ids": ["skill:api-guidelines-skill"],
                        "exit_gate": "contract-ready",
                    },
                    {
                        "phase_id": "verify",
                        "primary_skill_id": "skill:qa-test-planner",
                        "support_skill_ids": ["skill:playwright"],
                        "exit_gate": "tests-passed",
                    },
                ],
            },
        }],
    }), encoding="utf-8")


class WorkflowFixture:
    def __init__(self, database: Path, context: RequestContext) -> None:
        self.database = database
        self.context = context
        self.service = LocalControlPlaneService(database)

    def rows(self, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            return list(connection.execute(sql, values).fetchall())

    def plan_single(
        self,
        *,
        key: str = "memory-single",
        routing_context: RoutingContextInput = RoutingContextInput(),
        explicit_skill_ids: tuple[str, ...] = ("skill:api-designer",),
        explicit_semantics: str | None = "only",
    ):
        return self.service.plan_work(PlanWork(
            context=self.context,
            objective="Build the confidential student API at /private/project",
            goal_binding_id=None,
            requested_work_mode="single",
            explicit_skill_ids=explicit_skill_ids,
            explicit_semantics=explicit_semantics,
            expected_state_version=0,
            idempotency_key=key,
            correlation_id=f"correlation-{key}",
            routing_context=routing_context,
        ))

    def plan_phased(self, *, key: str = "memory-phased"):
        write_phased_profile(self.database.parent)
        return self.service.plan_work(PlanWork(
            context=self.context,
            objective="Design and verify the API",
            goal_binding_id=None,
            requested_work_mode="phased",
            explicit_skill_ids=(),
            explicit_semantics=None,
            expected_state_version=0,
            idempotency_key=key,
            correlation_id=f"correlation-{key}",
            routing_context=RoutingContextInput(
                workspace_root=None,
                domains=("api",),
                tags=("backend",),
            ),
        ))

    def plan_native_goal(self, *, key: str = "memory-native"):
        return self.service.plan_work(PlanWork(
            context=self.context,
            objective="Continue native goal",
            goal_binding_id="goal:native",
            requested_work_mode="managed-goal",
            explicit_skill_ids=(),
            explicit_semantics=None,
            expected_state_version=0,
            idempotency_key=key,
            correlation_id=f"correlation-{key}",
            routing_context=RoutingContextInput(),
        ))

    def complete(self, plan) -> None:
        items = self.rows(
            "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
            (plan.workflow_run_id,),
        )
        for index, item in enumerate(items):
            check_ids = (
                (SINGLE_CHECK_ID,)
                if item["phase_id"] == "single-work"
                else self._phase_checks(plan.workflow_run_id, item["phase_id"])
            )
            self.service.record_work_event(RecordWorkEvent(
                context=self.context,
                workflow_run_id=plan.workflow_run_id,
                phase_id=item["phase_id"],
                observation=LocalProgressObservation(
                    item["work_item_id"], "start", (), None,
                ),
                activation_receipt_ref=None,
                expected_state_version=1,
                idempotency_key=f"start-{index}-{plan.workflow_run_id}",
                correlation_id=f"start-{index}",
            ))
            self.service.record_work_event(RecordWorkEvent(
                context=self.context,
                workflow_run_id=plan.workflow_run_id,
                phase_id=item["phase_id"],
                observation=LocalProgressObservation(
                    item["work_item_id"],
                    "submit",
                    check_ids,
                    "sensitive reported outcome /private/project",
                ),
                activation_receipt_ref=None,
                expected_state_version=2,
                idempotency_key=f"submit-{index}-{plan.workflow_run_id}",
                correlation_id=f"submit-{index}",
            ))
            self.service.evaluate_gate(EvaluateGate(
                context=self.context,
                workflow_run_id=plan.workflow_run_id,
                phase_id=item["phase_id"],
                expected_state_version=3,
                expected_plan_revision=1,
                expected_evidence_digest=local_evidence_digest(check_ids),
                evidence_refs=(),
                idempotency_key=f"gate-{index}-{plan.workflow_run_id}",
                correlation_id=f"gate-{index}",
            ))

    def _phase_checks(self, workflow_run_id: str, phase_id: str) -> tuple[str, ...]:
        row = self.rows(
            "SELECT planned_skill_tree_json FROM local_control_plans WHERE workflow_run_id=?",
            (workflow_run_id,),
        )[0]
        tree = json.loads(row["planned_skill_tree_json"])
        phase = next(item for item in tree if item["phase_id"] == phase_id)
        return (phase["exit_gate"],)
