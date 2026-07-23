from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from workflow_skill_router.host_integration.contracts import (
    HostIntegrationContractError,
    validate_host_manifest,
)
from workflow_skill_router.ports import HostIntegrationAdapterPort
from workflow_skill_router.service import RouterService
from workflow_skill_router.runtime import SystemClock, UuidFactory


@dataclass(frozen=True, slots=True)
class RouterCompositionPorts:
    """RouterService 的明確組合邊界；權威資料只能由伺服器端 Host adapter 提供。"""

    authorizer: object
    runtime_authority: object
    runtime_context: object
    artifacts: object
    snapshot_codec: object
    runtime_sync: object
    projections: object
    planner: object
    scheduler: object
    snapshots: object
    policies: object
    validation_context: object
    route_validator: object
    activation_preflight: object
    coordinator: object
    gate_context: object
    gate_evaluator: object
    gate_coordinator: object
    status_reader: object
    diagnostics_reader: object
    evaluation: object


def compose_router_service(ports: RouterCompositionPorts) -> RouterService:
    """透過單一且可稽核的正式組合根建立 RouterService。"""

    return RouterService(
        authorizer=ports.authorizer,
        runtime_authority=ports.runtime_authority,
        runtime_context=ports.runtime_context,
        artifacts=ports.artifacts,
        snapshot_codec=ports.snapshot_codec,
        runtime_sync=ports.runtime_sync,
        projections=ports.projections,
        planner=ports.planner,
        scheduler=ports.scheduler,
        snapshots=ports.snapshots,
        policies=ports.policies,
        validation_context=ports.validation_context,
        route_validator=ports.route_validator,
        activation_preflight=ports.activation_preflight,
        coordinator=ports.coordinator,
        gate_context=ports.gate_context,
        gate_evaluator=ports.gate_evaluator,
        gate_coordinator=ports.gate_coordinator,
        status_reader=ports.status_reader,
        diagnostics_reader=ports.diagnostics_reader,
        evaluation=ports.evaluation,
    )


def open(
    database: Path,
    artifact_root: Path,
    runtime_adapter: HostIntegrationAdapterPort,
    request_authorizer,
    instruction_content_resolver,
    artifact_protector,
    activation_preflight,
    evaluation_ports,
    clock=None,
    id_factory=None,
) -> RouterService:
    """唯一正式 factory；Host adapter 只能回傳明確的 RouterCompositionPorts。"""

    try:
        validate_host_manifest(runtime_adapter.host_manifest())
    except (AttributeError, TypeError, ValueError) as error:
        if isinstance(error, HostIntegrationContractError):
            raise
        raise HostIntegrationContractError() from error
    ports = runtime_adapter.build_router_ports(
        database=database,
        artifact_root=artifact_root,
        request_authorizer=request_authorizer,
        instruction_content_resolver=instruction_content_resolver,
        artifact_protector=artifact_protector,
        activation_preflight=activation_preflight,
        evaluation_ports=evaluation_ports,
        clock=clock or SystemClock(),
        id_factory=id_factory or UuidFactory(),
    )
    if not isinstance(ports, RouterCompositionPorts):
        raise TypeError("runtime adapter 必須回傳 RouterCompositionPorts")
    return compose_router_service(ports)
