from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from workflow_skill_router.bridge import serve
from workflow_skill_router.capabilities.models import RiskLevel
from workflow_skill_router.composition import RouterCompositionPorts, compose_router_service
from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.routing.models import (
    ExplicitSemantics,
    GoalRelation,
    RuntimeMode,
    SupportPolicy,
    TaskSignals,
    UserDirective,
)
from workflow_skill_router.routing.profiler import decide_request
from workflow_skill_router.schemas.artifacts import canonical_json_bytes
from workflow_skill_router.service_models import (
    NextWorkResult,
    PlanWorkResult,
    RouterDiagnostics,
    RouterStatusView,
)
from workflow_skill_router.tool_dispatch import ToolDispatcher


_SERVICE_SEMANTICS = {
    "preferred-primary": "use",
    "allowed-set": "only",
    "required-all": "all",
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def _execute_bridge(dispatcher: ToolDispatcher, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = StringIO("".join(
        json.dumps(call, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for call in calls
    ))
    output = StringIO()
    diagnostics = StringIO()
    serve(source, output, dispatcher, diagnostics)
    results = [json.loads(line) for line in output.getvalue().splitlines()]
    if len(results) != len(calls):
        raise RuntimeError("demo bridge response count mismatch")
    if any(result.get("error", {}).get("code") == "internal-error" for result in results):
        raise RuntimeError("demo bridge returned internal-error")
    return results


class _VerifiedAuthorizer:
    def authorize_read(self, context) -> None:
        if not context.session_id.startswith("public-demo-") or context.actor != "demo-export":
            raise PermissionError("request-context-unverified")

    def authorize_mutation(self, context, expected_state_version: int) -> None:
        self.authorize_read(context)
        if expected_state_version != 0:
            raise PermissionError("state-version-unverified")

    def authorize_reporting(self, context, observation) -> None:
        del observation
        self.authorize_read(context)


class _VerifiedPlanner:
    def __init__(self) -> None:
        self.plans: dict[str, PlanWorkResult] = {}

    def validate_and_persist(self, command) -> PlanWorkResult:
        workflow_run_id = _stable_id(
            "workflow",
            command.context.session_id,
            command.idempotency_key,
        )
        envelope = command.requested_work_mode or "single"
        result = PlanWorkResult(
            status="planned-verified-host-fixture",
            workflow_run_id=workflow_run_id,
            work_graph_id=_stable_id("work-graph", workflow_run_id),
            created_work_items=3 if envelope == "managed-goal" else 1,
            routing_envelope=envelope,
            selection_mode="explicit-locked" if command.explicit_skill_ids else "auto",
            support_consent_required=False,
            planned_skill_ids=command.explicit_skill_ids,
            runtime_mode="verified-host-fixture",
        )
        self.plans[workflow_run_id] = result
        return result


class _VerifiedScheduler:
    def next(self, query, require_resume_refresh: bool = True) -> NextWorkResult:
        del require_resume_refresh
        return NextWorkResult(
            "ready",
            (),
            {
                "work_item_id": _stable_id("work-item", query.workflow_run_id),
                "routing_envelope": "single",
                "status": "ready",
            },
        )


class _VerifiedStatusReader:
    def __init__(self, planner: _VerifiedPlanner) -> None:
        self._planner = planner

    def read(self, query) -> RouterStatusView:
        plan = self._planner.plans.get(query.workflow_run_id or "")
        return RouterStatusView(
            query.goal_binding_id,
            query.workflow_run_id,
            0 if plan is None else plan.created_work_items,
            None,
            False,
        )


class _NoopPort:
    def catch_up(self) -> None:
        return None

    def __getattr__(self, name):
        del name

        def method(*args, **kwargs):
            del args, kwargs
            return None

        return method


def _verified_host_fixture_dispatcher() -> ToolDispatcher:
    """建立完整 RouterService composition；輸出僅屬 fixture 證據。"""

    planner = _VerifiedPlanner()
    noop = _NoopPort()
    service = compose_router_service(RouterCompositionPorts(
        authorizer=_VerifiedAuthorizer(),
        runtime_authority=noop,
        runtime_context=noop,
        artifacts=noop,
        snapshot_codec=noop,
        runtime_sync=noop,
        projections=noop,
        planner=planner,
        scheduler=_VerifiedScheduler(),
        snapshots=noop,
        policies=noop,
        validation_context=noop,
        route_validator=noop,
        activation_preflight=noop,
        coordinator=noop,
        gate_context=noop,
        gate_evaluator=noop,
        gate_coordinator=noop,
        status_reader=_VerifiedStatusReader(planner),
        diagnostics_reader=lambda: RouterDiagnostics(0, 0, 0),
        evaluation=noop,
    ))
    service.runtime_profile = "verified-host-fixture"
    return ToolDispatcher(service)


class DemoScenarioExporter:
    def __init__(
        self,
        local_dispatcher: ToolDispatcher,
        verified_host_dispatcher: ToolDispatcher,
    ) -> None:
        self._local_dispatcher = local_dispatcher
        self._verified_host_dispatcher = verified_host_dispatcher

    def export(self, item: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
        signals = TaskSignals(**{
            **item["signals"],
            "risk": RiskLevel(item["signals"]["risk"]),
        })
        explicit = tuple(item.get("explicit_skills", ()))
        semantics = (
            ExplicitSemantics(item["explicit_semantics"])
            if item.get("explicit_semantics")
            else None
        )
        support_policy = (
            SupportPolicy.AUTO
            if not explicit
            else SupportPolicy.FORBID
            if semantics is ExplicitSemantics.ALLOWED_SET
            else SupportPolicy.ASK
        )
        directive = UserDirective(
            None,
            explicit,
            semantics,
            support_policy,
            item["request"]["en"],
        )
        decision = decide_request(
            GoalRelation(item["goal_relation"]),
            signals,
            directive,
            RuntimeMode.HYBRID,
        )
        if decision.routing is None:
            raise ValueError("demo scenario must produce a routed-work decision")

        trace = self._record_trace(item, decision.routing.envelope.value)
        planned = trace["mcp_results"][0]
        if not planned["ok"]:
            raise RuntimeError(f"demo plan_work failed: {item['id']}")
        plan_result = planned["result"]
        route = {
            "envelope": plan_result["routing_envelope"],
            "primary_selection": item["primary"],
            "primary_selection_source": (
                "explicit-directive" if explicit else "scenario-capability-fixture"
            ),
            "support_selections": [],
            "selection_mode": plan_result["selection_mode"],
        }
        events = [{
            "event_type": "ROUTE_DECIDED",
            "payload": {
                "envelope": route["envelope"],
                "trace_request_id": trace["mcp_calls"][0]["request_id"],
            },
        }]
        branches = self._branches(item, support_policy, route, events)
        result = {
            "id": item["id"],
            "title": item["title"],
            "request": item["request"],
            "decision": {
                "goal_relation": decision.goal_relation.value,
                "execution_kind": decision.execution_kind.value,
                "envelope": plan_result["routing_envelope"],
            },
            "branches": branches,
            "phases": item.get("phases", []),
            "work_items": item.get("work_items", []),
            **trace,
        }
        if item["id"] == "real-model-evaluation":
            result["evaluation"] = {
                key: value
                for key, value in evaluation.items()
                if key not in {"score", "trusted", "reviewer_id", "raw_traces"}
            }
            result["evaluation"]["source_digest"] = (
                "sha256:" + sha256(canonical_json_bytes(evaluation)).hexdigest()
            )
        result["trace_digest"] = "sha256:" + sha256(canonical_json_bytes(result)).hexdigest()
        return result

    def _record_trace(self, item: Mapping[str, Any], envelope: str) -> dict[str, Any]:
        verified_host = item.get("runtime_fixture") == "verified-host"
        dispatcher = self._verified_host_dispatcher if verified_host else self._local_dispatcher
        scenario_id = str(item["id"])
        context = {
            "session_id": f"public-demo-{scenario_id}",
            "actor": "demo-export",
            "runtime_policy_snapshot_id": "public-demo-policy-v2",
        }
        goal_binding_id = (
            _stable_id("goal", scenario_id) if envelope == "managed-goal" else None
        )
        plan_call = {
            "request_id": f"{scenario_id}:01",
            "tool": "plan_work",
            "arguments": {
                "context": context,
                "objective": item["request"]["en"],
                "goal_binding_id": goal_binding_id,
                "requested_work_mode": envelope,
                "explicit_skill_ids": list(item.get("explicit_skills", ())),
                "explicit_semantics": _SERVICE_SEMANTICS.get(item.get("explicit_semantics")),
                "expected_state_version": 0,
                "idempotency_key": f"demo-plan-{scenario_id}",
                "correlation_id": f"demo-correlation-{scenario_id}",
            },
        }
        calls = [plan_call]
        results = _execute_bridge(dispatcher, [plan_call])
        if not results[0]["ok"]:
            return self._trace_metadata(verified_host, calls, results)

        workflow_run_id = results[0]["result"]["workflow_run_id"]
        follow_up_calls: list[dict[str, Any]] = []
        if envelope == "managed-goal":
            follow_up_calls.append({
                "request_id": f"{scenario_id}:02",
                "tool": "get_next_work",
                "arguments": {
                    "context": context,
                    "workflow_run_id": workflow_run_id,
                },
            })
        follow_up_calls.append({
            "request_id": f"{scenario_id}:{len(follow_up_calls) + 2:02d}",
            "tool": "get_router_status",
            "arguments": {
                "context": context,
                "goal_binding_id": goal_binding_id,
                "workflow_run_id": workflow_run_id,
            },
        })
        calls.extend(follow_up_calls)
        results.extend(_execute_bridge(dispatcher, follow_up_calls))
        return self._trace_metadata(verified_host, calls, results)

    @staticmethod
    def _trace_metadata(
        verified_host: bool,
        calls: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "mcp_calls": calls,
            "mcp_results": results,
            "runtime_profile": (
                "verified-host-fixture" if verified_host else "bundled-local-r0"
            ),
            "evidence_class": "fixture-trace" if verified_host else "runtime-trace",
            "trace_source": "verified-core-fixture" if verified_host else "router-core",
            "trace_status": "sanitized",
            "requires_host_capabilities": verified_host,
        }

    def _branches(
        self,
        item: Mapping[str, Any],
        support_policy: SupportPolicy,
        route: Mapping[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        support = item.get("support")
        if support and support_policy is SupportPolicy.AUTO:
            automatic_route = {**route, "support_selections": [support]}
            automatic_events = [
                *events,
                {
                    "event_type": "SUPPORT_SKILL_AUTO_SELECTED",
                    "payload": {
                        "capability_id": support,
                        "origin": "router-recommended",
                    },
                },
            ]
            return [self._branch(
                "default",
                automatic_route,
                automatic_events,
                "已自動選入最小必要輔助能力",
                "Minimal support auto-selected",
            )]
        if support and support_policy is SupportPolicy.ASK:
            proposal = {
                "event_type": "SUPPORT_SKILL_PROPOSED",
                "payload": {
                    "capability_id": support,
                    "origin": "router-recommended",
                },
            }
            rejected_events = [
                *events,
                proposal,
                {
                    "event_type": "SUPPORT_SKILL_REJECTED",
                    "payload": {"capability_id": support},
                },
            ]
            approved_events = [
                *events,
                proposal,
                {
                    "event_type": "SUPPORT_SKILL_APPROVED",
                    "payload": {"capability_id": support},
                },
                {
                    "event_type": "CAPABILITY_ACTIVATION_OBSERVED",
                    "payload": {"capability_id": support},
                },
            ]
            return [
                self._branch(
                    "support-rejected",
                    {**route, "support_selections": []},
                    rejected_events,
                    "僅使用指定 SKILL",
                    "Requested SKILL only",
                ),
                self._branch(
                    "support-approved",
                    {**route, "support_selections": [support]},
                    approved_events,
                    "已核准輔助能力",
                    "Support approved",
                ),
            ]
        return [self._branch("default", route, events, "路由已就緒", "Route ready")]

    @staticmethod
    def _branch(branch_id, route, events, status_zh, status_en):
        return {
            "branch_id": branch_id,
            "route": route,
            "events": events,
            "explicit_skill_coverage": {"status": "satisfied"},
            "status": {"en": status_en, "zh-TW": status_zh},
        }


def build_demo_artifact(
    source: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    with TemporaryDirectory(prefix="workflow-skill-router-demo-") as temporary:
        local_service = LocalControlPlaneService(Path(temporary) / "router.db")
        exporter = DemoScenarioExporter(
            ToolDispatcher(local_service),
            _verified_host_fixture_dispatcher(),
        )
        output = {
            "schema_id": "workflow-skill-router/demo-data",
            "schema_version": "2.0.0-alpha.1",
            "artifact_kind": "interactive-demo",
            "schema_revision": "router-v2-alpha-1",
            "runtime_input_digest": (
                "sha256:" + sha256(canonical_json_bytes(source)).hexdigest()
            ),
            "presets": [exporter.export(item, evaluation) for item in source["presets"]],
        }
    output["router_core_digest"] = "sha256:" + sha256(canonical_json_bytes({
        "module": "demo_export",
        "version": "2.0.0-alpha.1",
    })).hexdigest()
    return output
