from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from workflow_skill_router.capabilities.models import RiskLevel
from workflow_skill_router.routing.models import (
    ExplicitSemantics, GoalRelation, RuntimeMode, SupportPolicy, TaskSignals, UserDirective,
)
from workflow_skill_router.routing.profiler import decide_request
from workflow_skill_router.schemas.artifacts import canonical_json_bytes


class DemoScenarioExporter:
    def export(self, item: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
        signals = TaskSignals(**{**item["signals"], "risk": RiskLevel(item["signals"]["risk"])})
        explicit = tuple(item.get("explicit_skills", ()))
        semantics = ExplicitSemantics(item["explicit_semantics"]) if item.get("explicit_semantics") else None
        directive = UserDirective(None, explicit, semantics, SupportPolicy.ASK, item["request"]["en"])
        decision = decide_request(GoalRelation(item["goal_relation"]), signals, directive, RuntimeMode.HYBRID)
        route = {"envelope": decision.routing.envelope.value, "primary_selection": item["primary"],
                 "support_selections": [], "selection_mode": decision.routing.skill_policy.value}
        events = [{"event_type":"ROUTE_DECIDED","payload":{"envelope":route["envelope"]}}]
        branches = []
        support = item.get("support")
        if support:
            proposal = {"event_type":"SUPPORT_SKILL_PROPOSED","payload":{"capability_id":support,"origin":"router-recommended"}}
            rejected_events = [*events, proposal, {"event_type":"SUPPORT_SKILL_REJECTED","payload":{"capability_id":support}}]
            approved_events = [*events, proposal, {"event_type":"SUPPORT_SKILL_APPROVED","payload":{"capability_id":support}},
                               {"event_type":"CAPABILITY_ACTIVATION_OBSERVED","payload":{"capability_id":support}}]
            branches = [
                self._branch("support-rejected", {**route, "support_selections": []}, rejected_events, "僅使用指定 SKILL", "Requested SKILL only"),
                self._branch("support-approved", {**route, "support_selections": [support]}, approved_events, "已核准輔助能力", "Support approved"),
            ]
        else:
            branches = [self._branch("default", route, events, "路由已就緒", "Route ready")]
        result = {"id":item["id"],"title":item["title"],"request":item["request"],
                  "decision":{"goal_relation":decision.goal_relation.value,"execution_kind":decision.execution_kind.value,
                              "envelope":decision.routing.envelope.value},"branches":branches,
                  "phases":item.get("phases",[]),"work_items":item.get("work_items",[])}
        if item["id"] == "real-model-evaluation":
            result["evaluation"] = {key:value for key,value in evaluation.items() if key not in {"score","trusted","reviewer_id"}}
        result["trace_digest"] = "sha256:" + sha256(canonical_json_bytes(result)).hexdigest()
        return result

    @staticmethod
    def _branch(branch_id, route, events, status_zh, status_en):
        return {"branch_id":branch_id,"route":route,"events":events,
                "explicit_skill_coverage":{"status":"satisfied"},
                "status":{"en":status_en,"zh-TW":status_zh}}


def build_demo_artifact(source: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
    exporter = DemoScenarioExporter()
    output = {"schema_id":"workflow-skill-router/demo-data","schema_version":"2.0.0-alpha.1",
              "artifact_kind":"interactive-demo","schema_revision":"router-v2-alpha-1",
              "runtime_input_digest":"sha256:" + sha256(canonical_json_bytes(source)).hexdigest(),
              "presets":[exporter.export(item,evaluation) for item in source["presets"]]}
    output["router_core_digest"] = "sha256:" + sha256(canonical_json_bytes({"module":"demo_export","version":"2.0.0-alpha.1"})).hexdigest()
    return output
