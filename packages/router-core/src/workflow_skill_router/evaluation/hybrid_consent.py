from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.schemas.artifacts import canonical_json
from workflow_skill_router.tool_dispatch import ToolDispatcher


@dataclass(frozen=True, slots=True)
class HybridConsentBinding:
    proposal_id: str
    phase_id: str
    scope_anchor_id: str
    goal_revision: int | None
    plan_revision: int
    context_fingerprint: str
    rationale: str


class HybridConsentEvaluationController:
    """以公開 MCP command contract 將模型 intent 套用到持久化 proposal。"""

    def __init__(self, database: Path, *, session_id: str) -> None:
        self._session_id = session_id
        self._dispatcher = ToolDispatcher(LocalControlPlaneService(database))

    def persist_proposal(
        self,
        route: Mapping[str, object],
        *,
        context_fingerprint: str,
    ) -> tuple[HybridConsentBinding, dict[str, object]]:
        support = route.get("support_skills")
        if (
            route.get("selection_mode") != "explicit-locked"
            or route.get("consent_action") != "proposal-required"
            or not isinstance(support, list)
            or not support
            or not all(isinstance(item, str) and item for item in support)
        ):
            raise ValueError("hybrid_consent_proposal_invalid")
        primary = route.get("primary_skill")
        envelope = route.get("envelope")
        goal_relation = route.get("goal_relation")
        rationale = route.get("rationale")
        if (
            not isinstance(primary, str)
            or not primary
            or envelope not in {"single", "phased", "managed-goal"}
            or goal_relation not in {"none", "progress"}
            or not isinstance(rationale, str)
            or not rationale
        ):
            raise ValueError("hybrid_consent_proposal_invalid")

        identity = sha256(canonical_json({
            "context_fingerprint": context_fingerprint,
            "route": dict(route),
            "session_id": self._session_id,
        }).encode("utf-8")).hexdigest()
        context = self._context()
        goal_binding_id = f"evaluation-goal:{identity[:16]}" if goal_relation == "progress" else None
        goal_revision = 1 if goal_binding_id is not None else None
        plan = self._dispatcher.dispatch("plan_work", {
            "context": context,
            "objective": f"sealed-evaluation-route:{identity}",
            "goal_binding_id": goal_binding_id,
            "requested_work_mode": envelope,
            "explicit_skill_ids": [primary],
            "explicit_semantics": "use",
            "expected_state_version": 0,
            "idempotency_key": f"hybrid-plan:{identity}",
            "correlation_id": f"hybrid-plan:{identity[:24]}",
        })
        phase_id = f"evaluation-phase:{identity[:16]}"
        scope_anchor_id = f"scope:{phase_id}"
        proposed = self._dispatcher.dispatch("propose_support_consent", {
            "context": context,
            "workflow_run_id": plan["workflow_run_id"],
            "phase_id": phase_id,
            "scope_anchor_id": scope_anchor_id,
            "goal_revision": goal_revision,
            "plan_revision": 1,
            "primary_skill_id": primary,
            "support_skill_ids": support,
            "context_fingerprint": context_fingerprint,
            "expected_state_version": 1,
            "idempotency_key": f"hybrid-proposal:{identity}",
            "correlation_id": f"hybrid-proposal:{identity[:24]}",
        })
        binding = HybridConsentBinding(
            proposal_id=str(proposed["proposal_id"]),
            phase_id=phase_id,
            scope_anchor_id=scope_anchor_id,
            goal_revision=goal_revision,
            plan_revision=1,
            context_fingerprint=context_fingerprint,
            rationale=rationale,
        )
        return binding, self._route(proposed, rationale)

    def apply_intent(
        self,
        binding: HybridConsentBinding,
        intent: str,
    ) -> dict[str, object]:
        actions = {"approved": "approve", "rejected": "reject"}
        action = actions.get(intent)
        if action is None:
            raise ValueError("consent_intent_invalid")
        identity = sha256(
            f"{binding.proposal_id}\0{action}".encode("utf-8")
        ).hexdigest()
        result = self._dispatcher.dispatch("transition_support_consent", {
            "context": self._context(),
            "proposal_id": binding.proposal_id,
            "action": action,
            "current_phase_id": binding.phase_id,
            "current_scope_anchor_id": binding.scope_anchor_id,
            "current_goal_revision": binding.goal_revision,
            "current_plan_revision": binding.plan_revision,
            "current_context_fingerprint": binding.context_fingerprint,
            "expected_state_version": 1,
            "idempotency_key": f"hybrid-transition:{identity}",
            "correlation_id": f"hybrid-transition:{identity[:24]}",
        })
        return self._route(result, binding.rationale)

    def _context(self) -> dict[str, str]:
        return {
            "session_id": self._session_id,
            "actor": "model-evaluation",
            "runtime_policy_snapshot_id": "evaluation-hybrid-consent-v1",
        }

    @staticmethod
    def _route(result: Mapping[str, object], rationale: str) -> dict[str, object]:
        return {
            "envelope": result["routing_envelope"],
            "selection_mode": result["selection_mode"],
            "primary_skill": result["primary_skill"],
            "support_skills": list(result["support_skills"]),
            "consent_action": result["consent_action"],
            "goal_relation": result["goal_relation"],
            "rationale": rationale,
        }
