from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import uuid

from workflow_skill_router.routing.models import ExecutionKind, GoalRelation

from .models import GoalBinding, WorkGraph, WorkItem
from .relations import CONTROL_QUERY_RELATIONS, DETACHED_RELATIONS, SEMANTIC_MUTATION_ALLOWED


class InvalidWorkGraph(ValueError):
    pass


def _objective_digest(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Goal objective 不可為空")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GoalMessageDecision:
    binding: GoalBinding
    relation: GoalRelation
    execution_kind: str
    audit_event_type: str
    replacement_graph: WorkGraph | None
    detached_read_only: bool


@dataclass(frozen=True, slots=True)
class GoalReconcileResult:
    binding: GoalBinding
    graph: WorkGraph
    audit_event_type: str


class GoalOrchestrator:
    def __init__(self, *, clock=None, id_factory=None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))

    def _binding(
        self,
        objective: str,
        status: str,
        budget: str | None,
        *,
        source: str,
        host_goal_id: str | None,
        host_goal_revision: str | None,
    ) -> GoalBinding:
        now = self._clock()
        return GoalBinding(
            goal_binding_id=f"goal-binding:{self._id_factory()}",
            host_goal_id=host_goal_id,
            goal_revision=1,
            host_goal_revision=host_goal_revision,
            objective_digest=_objective_digest(objective),
            objective_snapshot=objective.strip(),
            status_snapshot=status,
            budget_snapshot=budget,
            synced_at=now.astimezone(timezone.utc).isoformat(),
            source=source,
        )

    def bind_native(
        self,
        host_goal_id: str | None,
        host_goal_revision: str | None,
        objective: str,
        status: str,
        budget: str | None,
    ) -> GoalBinding:
        if not host_goal_id or not host_goal_revision:
            raise ValueError("native Goal binding 需要 host identity 與 revision")
        return self._binding(
            objective, status, budget, source="native",
            host_goal_id=host_goal_id, host_goal_revision=host_goal_revision,
        )

    def bind_managed(
        self,
        objective: str,
        status: str,
        budget: str | None,
    ) -> GoalBinding:
        return self._binding(
            objective, status, budget, source="managed",
            host_goal_id=None, host_goal_revision=None,
        )

    @staticmethod
    def classify_relation(relation: GoalRelation) -> GoalRelation:
        if not isinstance(relation, GoalRelation):
            raise TypeError("relation 必須是 GoalRelation")
        return relation

    def observe_message(
        self,
        binding: GoalBinding,
        relation: GoalRelation,
        message: str,
    ) -> GoalMessageDecision:
        del message
        if relation in CONTROL_QUERY_RELATIONS:
            return GoalMessageDecision(
                binding, relation, ExecutionKind.CONTROL_QUERY.value,
                "GOAL_SIDE_QUERY_OBSERVED", None, True,
            )
        if relation in DETACHED_RELATIONS or relation is GoalRelation.NONE:
            return GoalMessageDecision(
                binding, relation, ExecutionKind.ROUTED_WORK.value,
                "GOAL_DETACHED_MESSAGE_OBSERVED", None, True,
            )
        if relation in SEMANTIC_MUTATION_ALLOWED:
            revised = replace(binding, goal_revision=binding.goal_revision + 1)
            return GoalMessageDecision(
                revised, relation, ExecutionKind.ROUTED_WORK.value,
                "GOAL_SEMANTIC_MESSAGE_OBSERVED", None, False,
            )
        raise ValueError("unsupported Goal relation")

    def validate_graph(self, items: tuple[WorkItem, ...]) -> tuple[str, ...]:
        by_id = {item.work_item_id: item for item in items}
        if len(by_id) != len(items):
            raise InvalidWorkGraph("duplicate Work Item id")
        for item in items:
            missing = set(item.dependency_ids) - set(by_id)
            if missing:
                raise InvalidWorkGraph(f"missing dependencies: {sorted(missing)}")
        indegree = {item.work_item_id: len(item.dependency_ids) for item in items}
        outgoing = {item.work_item_id: [] for item in items}
        for item in items:
            for dependency in item.dependency_ids:
                outgoing[dependency].append(item.work_item_id)
        ready = sorted(item_id for item_id, degree in indegree.items() if degree == 0)
        ordered = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for child in sorted(outgoing[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        if len(ordered) != len(items):
            raise InvalidWorkGraph("Work Graph contains cycle")

        concurrently_ready = [item for item in items if item.status == "ready"]
        for index, first in enumerate(concurrently_ready):
            for second in concurrently_ready[index + 1:]:
                overlap = set(first.write_resources) & set(second.write_resources)
                if overlap:
                    raise InvalidWorkGraph(
                        f"overlapping ready write resource: {sorted(overlap)}"
                    )
        return tuple(ordered)

    def reconcile(
        self,
        binding: GoalBinding,
        graph: WorkGraph,
        objective: str,
        host_goal_revision: str | None,
    ) -> GoalReconcileResult:
        if binding.source == "native" and not host_goal_revision:
            raise ValueError("native reconciliation 需要新的 host revision")
        revision = binding.goal_revision + 1
        digest = _objective_digest(objective)
        revised_binding = replace(
            binding,
            goal_revision=revision,
            host_goal_revision=host_goal_revision if binding.source == "native" else None,
            objective_digest=digest,
            objective_snapshot=objective.strip(),
            synced_at=self._clock().astimezone(timezone.utc).isoformat(),
        )
        revised_items = []
        for item in graph.items:
            if item.status == "completed":
                revised_items.append(item)
            elif item.status == "active":
                revised_items.append(replace(item, status="paused"))
            else:
                revised_items.append(replace(
                    item,
                    work_item_id=f"{item.work_item_id}:r{revision}",
                    status="pending",
                    phase_ids=(),
                ))
        remap = {
            old.work_item_id: new.work_item_id
            for old, new in zip(graph.items, revised_items)
        }
        revised_items = [
            replace(item, dependency_ids=tuple(remap.get(dep, dep) for dep in item.dependency_ids))
            for item in revised_items
        ]
        revised_graph = WorkGraph(
            f"{graph.work_graph_id}:r{revision}",
            graph.goal_binding_id,
            digest,
            graph.plan_revision + 1,
            graph.acceptance_coverage_ref,
            tuple(revised_items),
        )
        self.validate_graph(revised_graph.items)
        return GoalReconcileResult(
            revised_binding, revised_graph, "GOAL_REVISION_RECONCILED",
        )

    def get_next_work(self, graph: WorkGraph) -> WorkItem | None:
        self.validate_graph(graph.items)
        completed = {
            item.work_item_id for item in graph.items if item.status == "completed"
        }
        candidates = sorted(
            (
                item for item in graph.items
                if item.status in {"pending", "ready"}
                and set(item.dependency_ids) <= completed
            ),
            key=lambda item: (item.milestone_id, item.work_item_id),
        )
        return candidates[0] if candidates else None
