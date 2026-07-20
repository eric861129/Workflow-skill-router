from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
import types
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from workflow_skill_router.capabilities.agent_runtime import decode_agent_runtime_snapshot
from workflow_skill_router.service_models import (
    CompareEvaluations, EvaluateGate, ExportRouterArtifact, NextWorkQuery, PlanWork,
    ProposeSupportConsent, RecordWorkEvent, RequestContext, RouterStatusQuery,
    RoutingContextInput,
    RunModelEvaluation, TransitionSupportConsent,
    RuntimeContextSyncIntent, SyncRuntimeContext, ValidateRoute,
)
from workflow_skill_router.workflow.observations import (
    ActivationObservation, EvidenceObservation, PauseRequestObservation,
    SideEffectIntentObservation, SideEffectOutcomeObservation,
)


class ServiceCodecError(ValueError):
    pass


def _decode(value: Any, expected: Any) -> Any:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args: return None
        failures = []
        for item in args:
            if item is type(None): continue
            try: return _decode(value, item)
            except (ServiceCodecError, TypeError, ValueError) as error: failures.append(error)
        raise ServiceCodecError("union value 無法辨識")
    if origin is tuple:
        if not isinstance(value, list): raise ServiceCodecError("tuple field 必須是 array")
        item_type = args[0] if args else Any
        return tuple(_decode(item, item_type) for item in value)
    if expected is Any or expected is object: return value
    if expected is datetime:
        if not isinstance(value, str): raise ServiceCodecError("datetime 必須是字串")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if is_dataclass(expected): return _decode_dataclass(expected, value)
    if expected in (str, int, bool, float):
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise ServiceCodecError(f"field 必須是 {expected.__name__}")
        return value
    return value


def _decode_dataclass(cls, value: Any):
    if not isinstance(value, Mapping): raise ServiceCodecError(f"{cls.__name__} 必須是 object")
    expected_fields = {field.name for field in fields(cls)}
    actual = {str(key) for key in value}
    if actual != expected_fields:
        raise ServiceCodecError(f"{cls.__name__} fields mismatch: missing={sorted(expected_fields-actual)}, unknown={sorted(actual-expected_fields)}")
    hints = get_type_hints(cls)
    return cls(**{field.name: _decode(value[field.name], hints[field.name]) for field in fields(cls)})


def _encode(value: Any) -> Any:
    if is_dataclass(value): return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum): return value.value
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, Mapping): return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_encode(item) for item in value]
    return value


class ServiceCodec:
    def __init__(self, command_type, *, custom_decoder=None) -> None:
        self._command_type = command_type
        self._custom_decoder = custom_decoder

    def decode(self, arguments: Mapping[str, Any]):
        try:
            return (self._custom_decoder or (lambda value: _decode_dataclass(self._command_type, value)))(arguments)
        except (KeyError, TypeError, ValueError) as error:
            raise ServiceCodecError("invalid-arguments") from error

    def encode(self, result) -> Mapping[str, Any]:
        encoded = _encode(result)
        return encoded if isinstance(encoded, Mapping) else {"value": encoded}


def _sync(value):
    if not isinstance(value, Mapping) or set(value) != {field.name for field in fields(SyncRuntimeContext)}:
        raise ServiceCodecError("invalid-arguments")
    intent = value["intent"]
    if not isinstance(intent, Mapping) or set(intent) != {"host_snapshot_ref", "plugin_handshake_ref", "agent_runtime_snapshot"}:
        raise ServiceCodecError("invalid-arguments")
    return SyncRuntimeContext(
        _decode_dataclass(RequestContext, value["context"]),
        RuntimeContextSyncIntent(intent["host_snapshot_ref"], intent["plugin_handshake_ref"],
                                 decode_agent_runtime_snapshot(intent["agent_runtime_snapshot"])),
        _decode(value["expected_state_version"], int), _decode(value["idempotency_key"], str),
        _decode(value["correlation_id"], str),
    )


def _plan(value):
    if not isinstance(value, Mapping):
        raise ServiceCodecError("invalid-arguments")
    legacy_fields = {field.name for field in fields(PlanWork)} - {"routing_context"}
    actual = {str(key) for key in value}
    if not legacy_fields.issubset(actual) or actual - legacy_fields - {"routing_context"}:
        raise ServiceCodecError("invalid-arguments")
    normalized = dict(value)
    normalized.setdefault("routing_context", {
        "workspace_root": None,
        "domains": [],
        "tags": [],
        "current_phase_id": None,
    })
    return _decode_dataclass(PlanWork, normalized)


def build_service_codec_registry() -> Mapping[str, ServiceCodec]:
    return {
        "sync_runtime_context": ServiceCodec(SyncRuntimeContext, custom_decoder=_sync),
        "plan_work": ServiceCodec(PlanWork, custom_decoder=_plan),
        "propose_support_consent": ServiceCodec(ProposeSupportConsent),
        "transition_support_consent": ServiceCodec(TransitionSupportConsent),
        "get_next_work": ServiceCodec(NextWorkQuery),
        "validate_route": ServiceCodec(ValidateRoute),
        "record_work_event": ServiceCodec(RecordWorkEvent),
        "evaluate_gate": ServiceCodec(EvaluateGate),
        "get_router_status": ServiceCodec(RouterStatusQuery),
        "run_model_evaluation": ServiceCodec(RunModelEvaluation),
        "compare_evaluations": ServiceCodec(CompareEvaluations),
        "export_router_artifact": ServiceCodec(ExportRouterArtifact),
    }
