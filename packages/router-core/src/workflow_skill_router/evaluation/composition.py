from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationCompositionPorts:
    run_authorizer: object
    adapter_registry: object
    sealed_case_repository: object
    worker_broker: object
    isolation_verifier: object
    cancellation: object
    evaluation_store: object
    artifact_store: object
    release_policy: object
    scorer: object
    comparison_store: object
    trace_verifier: object
    collection_verifier: object
    review_verifiers: object
    clock: object
    id_factory: object


class EvaluationFacade:
    def __init__(self, ports: EvaluationCompositionPorts) -> None:
        self._ports = ports

    def run(self, command):
        authorization = self._ports.run_authorizer.validate_reference(command.context, command.authorization_ref)
        adapter = self._ports.adapter_registry.require(authorization.adapter_kind)
        case = self._ports.sealed_case_repository.require(command.sealed_case_ref)
        return self._ports.worker_broker.run(case, authorization, adapter, command.repeats)

    def compare(self, command):
        return self._ports.comparison_store.compare_authorized(command)

    def export(self, command):
        return self._ports.comparison_store.export_authorized(command)
