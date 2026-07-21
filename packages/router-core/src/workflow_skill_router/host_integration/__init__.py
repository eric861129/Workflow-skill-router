from workflow_skill_router.host_integration.contracts import (
    HOST_MANIFEST_SCHEMA,
    REFERENCE_AUTHORITY_LABEL,
    REQUIRED_HOST_PORTS,
    EventAppendProbe,
    HostConformanceCase,
    HostConformanceProbeInputs,
    HostConformanceReport,
    HostIntegrationConformanceError,
    HostIntegrationContractError,
    HostIntegrationManifest,
    HostPortRequirement,
    NativeGoalResumeProbe,
    ReceiptProbe,
    ServerOwnedHostResources,
    validate_host_manifest,
)


def run_host_conformance(*args, **kwargs):
    """延遲載入 conformance runner，避免組合根與整合套件互相匯入。"""

    from workflow_skill_router.host_integration.conformance import (
        run_host_conformance as _run_host_conformance,
    )

    return _run_host_conformance(*args, **kwargs)

__all__ = (
    "HOST_MANIFEST_SCHEMA",
    "REFERENCE_AUTHORITY_LABEL",
    "REQUIRED_HOST_PORTS",
    "EventAppendProbe",
    "HostConformanceCase",
    "HostConformanceProbeInputs",
    "HostConformanceReport",
    "HostIntegrationConformanceError",
    "HostIntegrationContractError",
    "HostIntegrationManifest",
    "HostPortRequirement",
    "NativeGoalResumeProbe",
    "ReceiptProbe",
    "ServerOwnedHostResources",
    "run_host_conformance",
    "validate_host_manifest",
)
