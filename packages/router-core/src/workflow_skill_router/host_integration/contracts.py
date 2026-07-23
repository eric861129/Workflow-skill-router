from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any


REFERENCE_AUTHORITY_LABEL = "reference-not-production-authority"
HOST_MANIFEST_SCHEMA = "workflow-skill-router/host-integration-manifest/1.0"
REQUIRED_HOST_PORTS = (
    "runtime_authority",
    "runtime_context",
    "scheduler",
    "snapshot_repository",
    "policy_repository",
    "route_validation",
    "activation_preflight",
    "activation_receipt_verification",
    "append_only_event_coordination",
    "gate_context",
    "gate_evaluator",
    "gate_coordinator",
    "artifact_protection",
    "evaluation",
)
_PUBLIC_DIAGNOSTIC = re.compile(r"^[a-z0-9-]+$")
_PUBLIC_PATH = re.compile(r"[A-Za-z]:\\|/(?:tmp|home|Users)/")
_FORBIDDEN_PUBLIC_KEYS = frozenset({
    "executable_path",
    "environment_value",
    "secret_value",
    "artifact_location",
    "receipt_authority_value",
})


class HostIntegrationContractError(ValueError):
    """Host integration manifest 或 server-owned 組合邊界無效。"""

    def __init__(self, diagnostic: str = "host-adapter-manifest-invalid") -> None:
        super().__init__(diagnostic)
        self.diagnostic = diagnostic


class HostIntegrationConformanceError(RuntimeError):
    """可安全公開的 Host conformance fail-closed 診斷。"""

    def __init__(self, diagnostic: str) -> None:
        if _PUBLIC_DIAGNOSTIC.fullmatch(diagnostic) is None:
            raise ValueError("public diagnostic 格式無效")
        super().__init__(diagnostic)
        self.diagnostic = diagnostic


@dataclass(frozen=True, slots=True)
class HostPortRequirement:
    port_name: str
    capability_id: str
    authority_owner: str
    trusted_input: str
    required_receipt: str
    freshness_condition: str
    fail_closed_behavior: str
    public_safe_diagnostic: str


@dataclass(frozen=True, slots=True)
class HostIntegrationManifest:
    schema_version: str
    adapter_id: str
    authority_label: str
    production_authority: bool
    server_owned_configuration: bool
    ports: tuple[HostPortRequirement, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ServerOwnedHostResources:
    """只由 Host composition root 建立，不屬於 MCP 或模型輸入契約。"""

    database: Path
    artifact_root: Path
    request_authorizer: object
    instruction_content_resolver: object
    artifact_protector: object
    activation_preflight: object
    evaluation_ports: object
    clock: object
    id_factory: object


@dataclass(frozen=True, slots=True)
class ReceiptProbe:
    context: object
    activation_receipt_ref: str
    route_id: str = ""


@dataclass(frozen=True, slots=True)
class EventAppendProbe:
    session_id: str
    expected_state_version: int
    idempotency_key: str
    payload_digest: str


@dataclass(frozen=True, slots=True)
class NativeGoalResumeProbe:
    context: object
    goal_binding_id: str
    refreshed_contexts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HostConformanceProbeInputs:
    """只提供 conformance 輸入；不得攜帶可被探測的 port 或 service。"""

    fresh_snapshot_ref: str
    stale_snapshot_ref: str
    valid_receipt_ref: str
    forged_receipt_ref: str
    valid_session_id: str
    wrong_session_id: str
    native_goal_id: str
    evaluation_mode: str = "unavailable"


@dataclass(frozen=True, slots=True)
class HostConformanceCase:
    name: str
    passed: bool
    diagnostic: str
    evidence: tuple[str, ...] = ()
    private_details: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, Any]:
        document = asdict(self)
        document.pop("private_details")
        return document


@dataclass(frozen=True, slots=True)
class HostConformanceReport:
    adapter_id: str
    authority_label: str
    status: str
    production_authority_declared: bool
    production_authority_verified: bool
    host_pilot_verified: bool
    hybrid_full: bool
    composition_root: str
    service_type: str
    cases: tuple[HostConformanceCase, ...]

    def case(self, name: str) -> HostConformanceCase:
        matches = tuple(item for item in self.cases if item.name == name)
        if len(matches) != 1:
            raise KeyError(name)
        return matches[0]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "authority_label": self.authority_label,
            "status": self.status,
            "production_authority_declared": self.production_authority_declared,
            "production_authority_verified": self.production_authority_verified,
            "host_pilot_verified": self.host_pilot_verified,
            "hybrid_full": self.hybrid_full,
            "composition_root": self.composition_root,
            "service_type": self.service_type,
            "cases": [item.to_public_dict() for item in self.cases],
        }


def validate_host_manifest(manifest: object) -> HostIntegrationManifest:
    if not isinstance(manifest, HostIntegrationManifest):
        raise HostIntegrationContractError()
    if (
        manifest.schema_version != HOST_MANIFEST_SCHEMA
        or not manifest.adapter_id.strip()
        or not manifest.authority_label.strip()
        or not isinstance(manifest.production_authority, bool)
        or manifest.server_owned_configuration is not True
    ):
        raise HostIntegrationContractError()
    names = tuple(item.port_name for item in manifest.ports)
    if len(names) != len(set(names)) or not set(REQUIRED_HOST_PORTS).issubset(names):
        raise HostIntegrationContractError()
    for item in manifest.ports:
        values = (
            item.port_name,
            item.capability_id,
            item.authority_owner,
            item.trusted_input,
            item.required_receipt,
            item.freshness_condition,
            item.fail_closed_behavior,
        )
        if any(not value.strip() for value in values):
            raise HostIntegrationContractError()
        if _PUBLIC_DIAGNOSTIC.fullmatch(item.public_safe_diagnostic) is None:
            raise HostIntegrationContractError()
    public = json.dumps(manifest.to_public_dict(), ensure_ascii=False, sort_keys=True)
    if _PUBLIC_PATH.search(public) or any(key in public for key in _FORBIDDEN_PUBLIC_KEYS):
        raise HostIntegrationContractError()
    return manifest
