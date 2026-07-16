from __future__ import annotations

from workflow_skill_router.capabilities.runtime_context import RuntimeContextSyncRequest
from workflow_skill_router.service_models import RecordWorkEventResult
from workflow_skill_router.workflow.coordinator import RecordObservationCommand


class RouterService:
    def __init__(
        self,
        *,
        authorizer,
        runtime_authority,
        runtime_context,
        artifacts,
        snapshot_codec,
        runtime_sync,
        projections,
        planner,
        scheduler,
        snapshots,
        policies,
        validation_context,
        route_validator,
        activation_preflight,
        coordinator,
        gate_context,
        gate_evaluator,
        gate_coordinator,
        status_reader,
        diagnostics_reader,
        evaluation,
    ) -> None:
        self._authorizer = authorizer
        self._runtime_authority = runtime_authority
        self._runtime_context = runtime_context
        self._artifacts = artifacts
        self._snapshot_codec = snapshot_codec
        self._runtime_sync = runtime_sync
        self._projections = projections
        self._planner = planner
        self._scheduler = scheduler
        self._snapshots = snapshots
        self._policies = policies
        self._validation_context = validation_context
        self._route_validator = route_validator
        self._activation_preflight = activation_preflight
        self._coordinator = coordinator
        self._gate_context = gate_context
        self._gate_evaluator = gate_evaluator
        self._gate_coordinator = gate_coordinator
        self._status_reader = status_reader
        self._diagnostics_reader = diagnostics_reader
        self._evaluation = evaluation

    def sync_runtime_context(self, command):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        authority = self._runtime_authority.require(command.context)
        request = RuntimeContextSyncRequest(
            authority=authority,
            host_snapshot_ref=command.intent.host_snapshot_ref,
            plugin_handshake_ref=command.intent.plugin_handshake_ref,
            agent_runtime_snapshot=command.intent.agent_runtime_snapshot,
        )
        result = self._runtime_context.sync_verified(request)
        snapshot_ref = self._artifacts.put_bytes(
            self._snapshot_codec.encode(result.snapshot),
            "application/json",
            "internal",
            "runtime-context",
        )
        self._runtime_sync.persist(command, result, snapshot_ref)
        self._projections.catch_up()
        return result

    def plan_work(self, command):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        return self._planner.validate_and_persist(command)

    def get_next_work(self, query):
        self._authorizer.authorize_read(query.context)
        return self._scheduler.next(query, require_resume_refresh=True)

    def validate_route(self, command):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        snapshot = self._snapshots.require(command.capability_snapshot_id)
        policy = self._policies.require(
            command.policy_revision,
            command.context.runtime_policy_snapshot_id,
        )
        validation = self._validation_context.current_for(command, snapshot, policy)
        result = self._route_validator.validate(
            command.route_proposal,
            snapshot,
            policy,
            validation,
        )
        return self._activation_preflight.bind_single_use_after_validation(
            command,
            result,
            snapshot,
        )

    def record_work_event(self, command):
        self._authorizer.authorize_reporting(command.context, command.observation)
        self._activation_preflight.verify_consumption_receipt(command)
        append = self._coordinator.record(RecordObservationCommand(
            command.workflow_run_id,
            command.phase_id,
            command.observation,
            command.expected_state_version,
            command.idempotency_key,
            command.correlation_id,
        ))
        self._projections.catch_up()
        return RecordWorkEventResult.from_append(append)

    def evaluate_gate(self, command):
        self._authorizer.authorize_mutation(command.context, command.expected_state_version)
        request = self._gate_context.build_from_current_projection(command)
        result = self._gate_evaluator.evaluate(request)
        return self._gate_coordinator.persist_result(command, result)

    def get_router_status(self, query):
        self._authorizer.authorize_read(query.context)
        self._projections.catch_up()
        return self._status_reader.read(query)

    def diagnostics(self):
        if callable(self._diagnostics_reader):
            return self._diagnostics_reader()
        return self._diagnostics_reader.read()

    def run_model_evaluation(self, command):
        self._authorizer.authorize_read(command.context)
        return self._evaluation.run(command)

    def compare_evaluations(self, command):
        self._authorizer.authorize_read(command.context)
        return self._evaluation.compare(command)

    def export_router_artifact(self, command):
        self._authorizer.authorize_read(command.context)
        return self._evaluation.export(command)
