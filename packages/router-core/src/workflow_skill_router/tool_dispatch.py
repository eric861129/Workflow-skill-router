from __future__ import annotations

from typing import Any, Mapping

from workflow_skill_router.service_codecs import build_service_codec_registry
from workflow_skill_router.runtime_readiness import (
    CapabilityUnavailable,
    RUNTIME_READINESS,
)


PUBLIC_TOOLS = (
    "sync_runtime_context", "plan_work", "propose_support_consent",
    "transition_support_consent", "get_next_work", "validate_route",
    "record_work_event", "evaluate_gate", "get_router_status",
    "run_model_evaluation", "compare_evaluations", "export_router_artifact",
)


class ToolDispatcher:
    def __init__(self, service) -> None:
        self._service = service
        self._codecs = build_service_codec_registry()

    def dispatch(self, tool: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if tool not in PUBLIC_TOOLS: raise LookupError(tool)
        if getattr(self._service, "runtime_profile", None) == "bundled-local-r0":
            if RUNTIME_READINESS[tool].availability != "local-ready":
                raise CapabilityUnavailable.for_tool(tool)
        command = self._codecs[tool].decode(arguments)
        result = getattr(self._service, tool)(command)
        return self._codecs[tool].encode(result)
