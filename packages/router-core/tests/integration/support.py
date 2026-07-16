from workflow_skill_router.composition import RouterCompositionPorts, compose_router_service
from workflow_skill_router.service import RouterService
from workflow_skill_router.service_models import (
    GoalStatusView, NextWorkResult, RouterDiagnostics, RouterStatusView,
)


class Authorizer:
    def authorize_read(self, context):
        if context.session_id != "session-1" or context.actor != "agent":
            raise PermissionError("request-context-unverified")
    def authorize_mutation(self, context, expected_state_version):
        self.authorize_read(context)
        if expected_state_version < 0: raise PermissionError("invalid-state-version")
    def authorize_reporting(self, context, observation):
        del observation
        self.authorize_read(context)


class Scheduler:
    def __init__(self): self.paused = set()
    def seed(self, workflow): self.paused.add(workflow)
    def next(self, query, require_resume_refresh=True):
        if require_resume_refresh and query.workflow_run_id in self.paused:
            return NextWorkResult("refresh-required", ("goal", "workspace", "capabilities", "evidence"), None)
        return NextWorkResult("ready", (), None)


class Status:
    def __init__(self): self.candidates = {}
    def read(self, query):
        return RouterStatusView(query.goal_binding_id, query.workflow_run_id, 0, self.candidates.get(query.goal_binding_id), False)


class Noop:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            del args, kwargs
            return None
        return method


def build_router_service():
    scheduler = Scheduler()
    status = Status()
    service = compose_router_service(RouterCompositionPorts(
        authorizer=Authorizer(), runtime_authority=Noop(), runtime_context=Noop(),
        artifacts=Noop(), snapshot_codec=Noop(), runtime_sync=Noop(), projections=Noop(),
        planner=Noop(), scheduler=scheduler, snapshots=Noop(), policies=Noop(),
        validation_context=Noop(), route_validator=Noop(), activation_preflight=Noop(),
        coordinator=Noop(), gate_context=Noop(), gate_evaluator=Noop(),
        gate_coordinator=Noop(), status_reader=status,
        diagnostics_reader=lambda: RouterDiagnostics(0, 0, 0),
    ))
    service._test_scheduler = scheduler
    service._test_status = status
    return service


def seed_paused_workflow(service, workflow_run_id, snapshot_id):
    del snapshot_id
    service._test_scheduler.seed(workflow_run_id)


def seed_complete_native_goal(service, goal_binding_id):
    service._test_status.candidates[goal_binding_id] = GoalStatusView(
        "candidate-1", "complete", "sha256:evidence",
    )
