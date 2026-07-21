import io
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from workflow_skill_router.bridge import serve
from workflow_skill_router.local_control import LocalControlPlaneService
from workflow_skill_router.service_models import (
    PlanWork,
    RecordWorkEvent,
    RequestContext,
    RoutingContextInput,
)
from workflow_skill_router.tool_dispatch import ToolDispatcher
from workflow_skill_router.workflow.local_observations import LocalProgressObservation
from workflow_skill_router.runtime_readiness import CapabilityUnavailable
from workflow_skill_router.schemas.artifacts import canonical_json


class FakeDispatcher:
    def __init__(self): self.calls = 0
    def dispatch(self, tool, arguments):
        self.calls += 1; return {"sequence": self.calls, "arguments": arguments}


class UnavailableDispatcher:
    def dispatch(self, tool, arguments):
        del tool, arguments
        raise CapabilityUnavailable.for_tool("get_next_work")


class BridgeTests(unittest.TestCase):
    def test_two_requests_share_one_dispatcher(self):
        source = io.StringIO('{"request_id":"r1","tool":"get_router_status","arguments":{}}\n'
                             '{"request_id":"r2","tool":"get_router_status","arguments":{}}\n')
        output = io.StringIO(); serve(source, output, FakeDispatcher())
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([1, 2], [row["result"]["sequence"] for row in rows])

    def test_unknown_tool_does_not_echo_secret(self):
        output = io.StringIO()
        serve(io.StringIO('{"request_id":"r1","tool":"raw_append","arguments":{"token":"secret"}}\n'), output, FakeDispatcher())
        self.assertEqual("unknown-tool", json.loads(output.getvalue())["error"]["code"])
        self.assertNotIn("secret", output.getvalue())

    def test_known_unavailable_capability_returns_public_safe_requirement(self):
        source = io.StringIO(
            '{"request_id":"r1","tool":"get_next_work","arguments":{}}\n'
        )
        output = io.StringIO()
        diagnostics = io.StringIO()
        serve(source, output, UnavailableDispatcher(), diagnostics)
        response = json.loads(output.getvalue())
        self.assertEqual("capability-unavailable", response["error"]["code"])
        self.assertEqual(
            "conditional-local", response["error"]["availability"]
        )
        self.assertEqual(
            ["router-owned-work-graph", "no-native-goal-authority-required"],
            response["error"]["required_capabilities"],
        )
        self.assertEqual("", diagnostics.getvalue())


class ConditionalLocalBridgeContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = Path(self.directory.name) / "router.db"
        self.service = LocalControlPlaneService(self.database)
        self.dispatcher = ToolDispatcher(self.service)
        self.context = RequestContext("session-public", "developer", "policy-public")
        self.public_context = {
            "session_id": self.context.session_id,
            "actor": self.context.actor,
            "runtime_policy_snapshot_id": self.context.runtime_policy_snapshot_id,
        }

    def tearDown(self):
        self.directory.cleanup()

    def plan(
        self,
        key: str,
        *,
        goal_binding_id: str | None = None,
        mode: str = "single",
        routing_context: RoutingContextInput = RoutingContextInput(),
    ):
        return self.service.plan_work(PlanWork(
            context=self.context,
            objective="Design and verify the API" if mode == "phased" else "Fix the API",
            goal_binding_id=goal_binding_id,
            requested_work_mode=mode,
            explicit_skill_ids=(),
            explicit_semantics=None,
            expected_state_version=0,
            idempotency_key=key,
            correlation_id=f"correlation-{key}",
            routing_context=routing_context,
        ))

    def item(self, workflow_run_id: str):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                "SELECT * FROM local_work_items WHERE workflow_run_id=? ORDER BY item_order",
                (workflow_run_id,),
            ).fetchone()

    def call(self, tool: str, arguments: dict[str, object]):
        source = io.StringIO(json.dumps({
            "request_id": f"request-{tool}",
            "tool": tool,
            "arguments": arguments,
        }) + "\n")
        output = io.StringIO()
        diagnostics = io.StringIO()
        serve(source, output, self.dispatcher, diagnostics)
        return json.loads(output.getvalue()), diagnostics.getvalue()

    def arguments(
        self,
        tool: str,
        workflow_run_id: str,
        *,
        item=None,
        suffix: str,
        expected_state_version: int = 1,
        expected_evidence_digest: str | None = None,
    ) -> dict[str, object]:
        if tool == "get_next_work":
            return {"context": self.public_context, "workflow_run_id": workflow_run_id}
        if tool == "record_work_event":
            return {
                "context": self.public_context,
                "workflow_run_id": workflow_run_id,
                "phase_id": "single-work" if item is None else item["phase_id"],
                "observation": {
                    "work_item_id": "work-item:missing" if item is None else item["work_item_id"],
                    "transition": "start",
                    "check_ids": [],
                    "reported_outcome": None,
                },
                "activation_receipt_ref": None,
                "expected_state_version": expected_state_version,
                "idempotency_key": f"record-{suffix}",
                "correlation_id": f"record-{suffix}",
            }
        return {
            "context": self.public_context,
            "workflow_run_id": workflow_run_id,
            "phase_id": "single-work" if item is None else item["phase_id"],
            "expected_state_version": expected_state_version,
            "expected_plan_revision": 1,
            "expected_evidence_digest": expected_evidence_digest or "sha256:" + "0" * 64,
            "evidence_refs": [],
            "idempotency_key": f"gate-{suffix}",
            "correlation_id": f"gate-{suffix}",
        }

    def write_phased_profile(self):
        profile_dir = self.database.parent / "profiles/personal"
        profile_dir.mkdir(parents=True)
        (profile_dir / "delivery.json").write_text(json.dumps({
            "schema_id": "workflow-skill-router/routing-profile",
            "schema_version": "1.0.0",
            "artifact_kind": "routing-profile",
            "profile_id": "personal:delivery",
            "scope": "personal",
            "enabled": True,
            "rules": [{
                "rule_id": "delivery",
                "priority": 50,
                "match": {
                    "objective_keywords": ["api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["phased"],
                },
                "route": {
                    "work_mode": "phased",
                    "skill_tree": [{
                        "phase_id": "design",
                        "primary_skill_id": "skill:api-designer",
                        "support_skill_ids": [],
                        "exit_gate": "contract-ready",
                    }],
                },
            }],
        }), encoding="utf-8")

    def test_router_owned_success_is_public_for_all_three_conditional_tools(self):
        next_plan = self.plan("public-next-success")
        next_response, _ = self.call(
            "get_next_work",
            self.arguments("get_next_work", next_plan.workflow_run_id, suffix="success"),
        )
        self.assertTrue(next_response["ok"])
        self.assertEqual("router-local", next_response["result"]["authority_mode"])

        record_plan = self.plan("public-record-success")
        record_item = self.item(record_plan.workflow_run_id)
        record_response, _ = self.call(
            "record_work_event",
            self.arguments(
                "record_work_event", record_plan.workflow_run_id,
                item=record_item, suffix="success",
            ),
        )
        self.assertTrue(record_response["ok"])
        self.assertEqual("router-local", record_response["result"]["authority_mode"])

        self.write_phased_profile()
        gate_plan = self.plan(
            "public-gate-success",
            mode="phased",
            routing_context=RoutingContextInput(domains=("api",)),
        )
        gate_item = self.item(gate_plan.workflow_run_id)
        self.service.record_work_event(RecordWorkEvent(
            self.context, gate_plan.workflow_run_id, gate_item["phase_id"],
            LocalProgressObservation(gate_item["work_item_id"], "start", (), None),
            None, 1, "gate-success-start", "gate-success-start",
        ))
        self.service.record_work_event(RecordWorkEvent(
            self.context, gate_plan.workflow_run_id, gate_item["phase_id"],
            LocalProgressObservation(
                gate_item["work_item_id"], "submit", ("contract-ready",), None,
            ),
            None, 2, "gate-success-submit", "gate-success-submit",
        ))
        evidence_digest = "sha256:" + hashlib.sha256(canonical_json({
            "evidence_class": "user-or-agent-reported-local",
            "persisted_check_ids": ["contract-ready"],
        }).encode("utf-8")).hexdigest()
        gate_response, _ = self.call(
            "evaluate_gate",
            self.arguments(
                "evaluate_gate", gate_plan.workflow_run_id, item=gate_item,
                suffix="success", expected_state_version=3,
                expected_evidence_digest=evidence_digest,
            ),
        )
        self.assertTrue(gate_response["ok"])
        self.assertEqual("router-local", gate_response["result"]["authority_mode"])

    def test_native_goal_uses_each_tools_established_verified_host_boundary(self):
        plan = self.plan(
            "public-native", goal_binding_id="native-goal:public", mode="managed-goal",
        )
        item = self.item(plan.workflow_run_id)
        expected = {
            "get_next_work": ["verified-host-scheduler"],
            "record_work_event": ["verified-event-store", "activation-receipt-verifier"],
            "evaluate_gate": ["verified-evidence-store", "gate-authority"],
        }
        for tool, capabilities in expected.items():
            response, diagnostics = self.call(
                tool,
                self.arguments(tool, plan.workflow_run_id, item=item, suffix="native"),
            )
            self.assertFalse(response["ok"])
            self.assertEqual("capability-unavailable", response["error"]["code"])
            self.assertEqual(capabilities, response["error"]["required_capabilities"])
            self.assertNotIn("router-owned-work-graph", response["error"]["required_capabilities"])
            self.assertEqual("", diagnostics)

    def test_missing_graph_requests_local_replay_or_creation_for_all_three_tools(self):
        for tool in ("get_next_work", "record_work_event", "evaluate_gate"):
            response, diagnostics = self.call(
                tool,
                self.arguments(tool, "workflow:missing", suffix=f"missing-{tool}"),
            )
            self.assertFalse(response["ok"])
            self.assertEqual("capability-unavailable", response["error"]["code"])
            self.assertEqual(
                ["router-owned-work-graph"], response["error"]["required_capabilities"],
            )
            self.assertRegex(response["error"]["fallback_action"], r"(?i)(create|replay)")
            self.assertNotRegex(response["error"]["fallback_action"], r"(?i)verified host")
            self.assertEqual("", diagnostics)

    def test_corrupt_graph_is_sanitized_as_internal_error_for_all_three_tools(self):
        plan = self.plan("public-corrupt")
        item = self.item(plan.workflow_run_id)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "UPDATE local_work_items SET status='completed' WHERE workflow_run_id=?",
                (plan.workflow_run_id,),
            )
            connection.commit()
        for tool in ("get_next_work", "record_work_event", "evaluate_gate"):
            response, diagnostics = self.call(
                tool,
                self.arguments(tool, plan.workflow_run_id, item=item, suffix=f"corrupt-{tool}"),
            )
            self.assertFalse(response["ok"])
            self.assertEqual("internal-error", response["error"]["code"])
            self.assertRegex(response["error"]["message"], r"^correlation:[0-9a-f]{16}$")
            self.assertNotIn("local-work-graph-corruption", json.dumps(response))
            self.assertNotIn("verified-host", json.dumps(response))
            self.assertIn("LocalWorkGraphCorruption", diagnostics)


if __name__ == "__main__": unittest.main()
