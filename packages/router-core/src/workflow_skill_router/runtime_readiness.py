from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ToolRuntimeReadiness:
    """描述公開工具在目前 runtime profile 的真實可執行邊界。"""

    tool_name: str
    availability: str
    risk_class: str
    required_capabilities: tuple[str, ...]
    fallback_action: str
    local_conditions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _entry(
    tool_name: str,
    availability: str,
    risk_class: str,
    required_capabilities: tuple[str, ...],
    fallback_action: str,
    local_conditions: tuple[str, ...] = (),
) -> ToolRuntimeReadiness:
    return ToolRuntimeReadiness(
        tool_name,
        availability,
        risk_class,
        required_capabilities,
        fallback_action,
        local_conditions,
    )


RUNTIME_READINESS: Mapping[str, ToolRuntimeReadiness] = {
    "sync_runtime_context": _entry(
        "sync_runtime_context",
        "verified-host-required",
        "R1",
        ("verified-host-runtime", "runtime-authority-receipt"),
        "Continue in bundled local R0 mode or initialize a verified host integration.",
    ),
    "plan_work": _entry(
        "plan_work",
        "local-ready",
        "R0",
        ("bundled-local-control-plane",),
        "Use the bundled durable local planner.",
    ),
    "propose_support_consent": _entry(
        "propose_support_consent",
        "local-ready",
        "R0",
        ("bundled-local-control-plane", "explicit-skill-plan"),
        "Persist a Phase-scoped support proposal before asking for user consent.",
    ),
    "transition_support_consent": _entry(
        "transition_support_consent",
        "local-ready",
        "R0",
        ("bundled-local-control-plane", "persisted-support-proposal"),
        "Apply approve or reject intent to the bound proposal without rewriting its route.",
    ),
    "get_next_work": _entry(
        "get_next_work",
        "conditional-local",
        "R0",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
        "Use a validated Router-owned graph or initialize the verified host scheduler.",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
    ),
    "validate_route": _entry(
        "validate_route",
        "verified-host-required",
        "R1",
        ("verified-capability-snapshot", "route-validation-authority"),
        "Preserve the route proposal and validate it after verified host initialization.",
    ),
    "record_work_event": _entry(
        "record_work_event",
        "conditional-local",
        "R0",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
        "Record advisory local progress or continue through the verified host event store.",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
    ),
    "evaluate_gate": _entry(
        "evaluate_gate",
        "conditional-local",
        "R0",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
        "Evaluate an advisory local gate or continue through verified host evidence authority.",
        ("router-owned-work-graph", "no-native-goal-authority-required"),
    ),
    "get_router_status": _entry(
        "get_router_status",
        "local-ready",
        "R0",
        ("bundled-local-control-plane",),
        "Read the bundled local planner status.",
    ),
    "run_model_evaluation": _entry(
        "run_model_evaluation",
        "configured-adapter-required",
        "R2",
        (
            "configured-evaluation-adapter",
            "sealed-evaluation-case",
            "trusted-subprocess-adapter-config",
        ),
        "Configure a trusted host-side adapter or report manual-required evidence.",
    ),
    "compare_evaluations": _entry(
        "compare_evaluations",
        "configured-adapter-required",
        "R1",
        ("verified-evaluation-runs", "evaluation-authorization"),
        "Import or run two authorized evaluation arms before comparison.",
    ),
    "export_router_artifact": _entry(
        "export_router_artifact",
        "configured-adapter-required",
        "R2",
        ("reviewed-evaluation-comparison", "export-attestation"),
        "Keep the artifact review-required until trusted attestation is available.",
    ),
}


class CapabilityUnavailable(RuntimeError):
    """可安全跨 bridge 回傳的 runtime capability 缺口。"""

    def __init__(self, readiness: ToolRuntimeReadiness) -> None:
        super().__init__("capability-unavailable")
        self.readiness = readiness

    @classmethod
    def for_tool(cls, tool_name: str) -> "CapabilityUnavailable":
        return cls(RUNTIME_READINESS[tool_name])

    @classmethod
    def for_local_condition(
        cls,
        tool_name: str,
        *,
        required_capabilities: tuple[str, ...],
        fallback_action: str,
    ) -> "CapabilityUnavailable":
        entry = RUNTIME_READINESS[tool_name]
        return cls(ToolRuntimeReadiness(
            tool_name=entry.tool_name,
            availability=entry.availability,
            risk_class=entry.risk_class,
            required_capabilities=required_capabilities,
            fallback_action=fallback_action,
            local_conditions=entry.local_conditions,
        ))

    def public_payload(self) -> dict[str, object]:
        entry = self.readiness
        return {
            "availability": entry.availability,
            "code": "capability-unavailable",
            "fallback_action": entry.fallback_action,
            "message": "The selected runtime cannot execute this tool.",
            "required_capabilities": list(entry.required_capabilities),
            "local_conditions": list(entry.local_conditions),
            "tool_name": entry.tool_name,
        }


def readiness_document() -> dict[str, dict[str, object]]:
    return {
        name: entry.to_dict()
        for name, entry in RUNTIME_READINESS.items()
    }
