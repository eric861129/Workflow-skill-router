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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _entry(
    tool_name: str,
    availability: str,
    risk_class: str,
    required_capabilities: tuple[str, ...],
    fallback_action: str,
) -> ToolRuntimeReadiness:
    return ToolRuntimeReadiness(
        tool_name,
        availability,
        risk_class,
        required_capabilities,
        fallback_action,
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
    "get_next_work": _entry(
        "get_next_work",
        "verified-host-required",
        "R0",
        ("verified-host-scheduler", "fresh-runtime-context"),
        "Inspect local status or initialize the verified host scheduler.",
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
        "verified-host-required",
        "R1",
        ("verified-event-store", "activation-receipt-verifier"),
        "Retain the observation locally and report it only through a verified host.",
    ),
    "evaluate_gate": _entry(
        "evaluate_gate",
        "verified-host-required",
        "R1",
        ("verified-evidence-store", "gate-authority"),
        "Keep the gate pending until verified evidence and state are available.",
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
        ("configured-evaluation-adapter", "sealed-evaluation-case"),
        "Configure a trusted adapter or report manual-required evidence.",
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

    def public_payload(self) -> dict[str, object]:
        entry = self.readiness
        return {
            "availability": entry.availability,
            "code": "capability-unavailable",
            "fallback_action": entry.fallback_action,
            "message": "The selected runtime cannot execute this tool.",
            "required_capabilities": list(entry.required_capabilities),
            "tool_name": entry.tool_name,
        }


def readiness_document() -> dict[str, dict[str, object]]:
    return {
        name: entry.to_dict()
        for name, entry in RUNTIME_READINESS.items()
    }
