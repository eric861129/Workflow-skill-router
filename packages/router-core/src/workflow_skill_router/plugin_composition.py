from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow_skill_router.composition import open as open_router


class BridgeInitializationError(PermissionError): pass


@dataclass(frozen=True, slots=True)
class VerifiedBridgeInitialization:
    session_id: str
    bundle_digest: str
    schema_digest: str
    runtime_adapter_id: str


def open_plugin_service(state_dir: Path, bridge_initialization_ref: str, host_registry_verifier):
    verified = host_registry_verifier.verify_initialization(bridge_initialization_ref)
    if not isinstance(verified, VerifiedBridgeInitialization):
        raise BridgeInitializationError("bridge_initialization_unverified")
    adapter = host_registry_verifier.resolve_runtime_adapter(verified.runtime_adapter_id)
    resources = host_registry_verifier.resolve_server_resources(verified)
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    return open_router(
        state_dir / "router.db", state_dir / "artifacts", adapter,
        resources.request_authorizer, resources.instruction_content_resolver,
        resources.artifact_protector, resources.activation_preflight,
        resources.evaluation_ports, resources.clock, resources.id_factory,
    )
