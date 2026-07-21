from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "remote_governance.py"
CLI_PATH = ROOT / "scripts" / "verify-remote-governance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("remote_governance", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_cli_module():
    spec = importlib.util.spec_from_file_location("verify_remote_governance", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def contract() -> dict[str, object]:
    return {
        "repository": "eric861129/Workflow-skill-router",
        "branch": "main",
        "required_status_checks": {
            "strict": True,
            "checks": [
                {"context": "Core, documentation, and policy contracts", "app_id": 15368},
                {"context": "Site visual regression", "app_id": 15368},
                {"context": "Required cross-platform V2 gate", "app_id": 15368},
            ],
        },
        "required_branch_controls": {
            "pull_request": True,
            "conversation_resolution": True,
            "force_pushes": False,
            "deletions": False,
        },
        "tag_protection": {
            "name": "Immutable V2 release tags",
            "target": "tag",
            "enforcement": "active",
            "ref_name_include": "refs/tags/v2.*",
            "required_rules": ["creation", "update", "deletion"],
            "required_bypass_actor": {
                "actor_id": 15368,
                "actor_type": "Integration",
                "bypass_mode": "always",
            },
        },
    }


def protected_branch() -> dict[str, object]:
    return {"protected": True}


def main_protection() -> dict[str, object]:
    return {
        "required_status_checks": {
            "strict": True,
            "checks": [
                {"context": "Core, documentation, and policy contracts", "app_id": 15368},
                {"context": "Site visual regression", "app_id": 15368},
                {"context": "Required cross-platform V2 gate", "app_id": 15368},
            ],
        },
        "required_pull_request_reviews": {"dismissal_restrictions": {}},
        "required_conversation_resolution": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }


def v2_tag_ruleset() -> dict[str, object]:
    return {
        "name": "Immutable V2 release tags",
        "target": "tag",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/tags/v2.*"]}},
        "rules": [{"type": "creation"}, {"type": "update"}, {"type": "deletion"}],
        "bypass_actors": [{"actor_id": 15368, "actor_type": "Integration", "bypass_mode": "always"}],
    }


def v2_tag_ruleset_summary() -> dict[str, object]:
    return {
        "id": 42,
        "name": "Immutable V2 release tags",
        "enforcement": "active",
    }


class RemoteGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.governance = load_module()
        cls.cli = load_cli_module()

    def test_evaluate_governance_accepts_complete_contract_payload(self) -> None:
        violations = self.governance.evaluate_governance(
            contract(), protected_branch(), main_protection(), [v2_tag_ruleset()]
        )

        self.assertEqual([], violations)

    def test_evaluate_governance_fails_closed_for_unprotected_main_and_missing_tag_ruleset(self) -> None:
        violations = self.governance.evaluate_governance(contract(), {"protected": False}, {}, [])

        self.assertIn("main-not-protected", violations)
        self.assertIn("v2-tag-ruleset-missing", violations)

    def test_missing_required_check_is_reported(self) -> None:
        protection = main_protection()
        protection["required_status_checks"]["checks"].pop()  # type: ignore[index]

        self.assertIn(
            "required-status-check-missing",
            self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]),
        )

    def test_legacy_contexts_are_accepted_only_when_all_expected_contexts_exist(self) -> None:
        protection = main_protection()
        protection["required_status_checks"] = {
            "strict": True,
            "contexts": [item["context"] for item in contract()["required_status_checks"]["checks"]],  # type: ignore[index]
        }

        self.assertEqual([], self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]))
        protection["required_status_checks"]["contexts"].pop()  # type: ignore[index]
        self.assertIn("required-status-check-missing", self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]))

    def test_branch_control_violations_fail_closed(self) -> None:
        cases = (
            ("required_pull_request_reviews", None, "direct-push-allowed"),
            ("allow_force_pushes", {"enabled": True}, "force-push-allowed"),
            ("allow_deletions", True, "deletion-allowed"),
            ("required_conversation_resolution", {"enabled": False}, "conversation-resolution-missing"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                protection = main_protection()
                if value is None:
                    del protection[field]
                else:
                    protection[field] = value
                self.assertIn(expected, self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]))

    def test_force_push_and_deletion_require_an_explicit_false_value(self) -> None:
        for field, expected in (
            ("allow_force_pushes", "force-push-allowed"),
            ("allow_deletions", "deletion-allowed"),
        ):
            missing = main_protection()
            del missing[field]
            self.assertIn(expected, self.governance.evaluate_governance(contract(), protected_branch(), missing, [v2_tag_ruleset()]))
            for value in (None, {}, {"enabled": None}, {"enabled": "false"}, True, {"enabled": True}):
                with self.subTest(field=field, value=value):
                    protection = main_protection()
                    protection[field] = value
                    self.assertIn(expected, self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]))
            for value in (False, {"enabled": False}):
                with self.subTest(field=field, compliant=value):
                    protection = main_protection()
                    protection[field] = value
                    self.assertNotIn(expected, self.governance.evaluate_governance(contract(), protected_branch(), protection, [v2_tag_ruleset()]))

    def test_inactive_or_incomplete_tag_ruleset_is_rejected(self) -> None:
        inactive = v2_tag_ruleset()
        inactive["enforcement"] = "evaluate"
        self.assertIn("v2-tag-ruleset-missing", self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [inactive]))

        missing_rule = v2_tag_ruleset()
        missing_rule["rules"] = [{"type": "creation"}, {"type": "update"}]
        self.assertIn("v2-tag-rule-missing", self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [missing_rule]))

    def test_missing_integration_bypass_is_rejected(self) -> None:
        ruleset = v2_tag_ruleset()
        ruleset["bypass_actors"] = []

        self.assertIn("v2-tag-bypass-missing", self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [ruleset]))

    def test_extra_bypass_actor_is_rejected(self) -> None:
        ruleset = v2_tag_ruleset()
        ruleset["bypass_actors"].append(  # type: ignore[index]
            {"actor_id": 1, "actor_type": "User", "bypass_mode": "always"}
        )

        self.assertIn("v2-tag-bypass-missing", self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [ruleset]))

    def test_tag_ruleset_name_must_match_the_contract(self) -> None:
        ruleset = v2_tag_ruleset()
        ruleset["name"] = "Other immutable tags"

        self.assertIn("v2-tag-ruleset-missing", self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [ruleset]))

    def test_later_eligible_tag_ruleset_can_satisfy_the_contract(self) -> None:
        incomplete = v2_tag_ruleset()
        incomplete["rules"] = [{"type": "creation"}]

        self.assertEqual([], self.governance.evaluate_governance(contract(), protected_branch(), main_protection(), [incomplete, v2_tag_ruleset()]))

    def test_load_contract_rejects_weakened_or_incomplete_contracts(self) -> None:
        mutations = (
            ("branch", "develop"),
            ("tag_protection.name", "Other tags"),
            ("tag_protection.target", "branch"),
            ("tag_protection.enforcement", "evaluate"),
            ("tag_protection.ref_name_include", ""),
            ("tag_protection.required_rules", []),
            ("tag_protection.required_rules", ["creation", ""]),
            ("tag_protection.required_bypass_actor.actor_id", 1),
            ("tag_protection.required_bypass_actor.actor_type", "User"),
            ("tag_protection.required_bypass_actor.bypass_mode", "pull_request"),
        )
        for dotted_path, value in mutations:
            with self.subTest(dotted_path=dotted_path):
                payload = contract()
                target = payload
                keys = dotted_path.split(".")
                for key in keys[:-1]:
                    target = target[key]  # type: ignore[index, assignment]
                target[keys[-1]] = value  # type: ignore[index]
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "contract.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        self.governance.load_contract(path)

    def test_cli_returns_public_safe_failure_for_malformed_nested_payloads(self) -> None:
        payload_sets = (
            (protected_branch(), {"required_status_checks": {"strict": True, "contexts": [["unhashable"]]}}, [v2_tag_ruleset()]),
            (protected_branch(), main_protection(), ["not-a-ruleset"]),
            ({"protected": ["not-a-boolean"]}, main_protection(), [v2_tag_ruleset()]),
        )
        for payloads in payload_sets:
            with self.subTest(payloads=payloads):
                output = io.StringIO()
                with patch.object(self.cli, "_load_governance_module", return_value=self.governance), patch.object(
                    self.governance, "fetch_json", side_effect=payloads
                ), redirect_stdout(output):
                    code = self.cli.main(["--repo", "eric861129/Workflow-skill-router"])
                self.assertEqual(1, code)
                self.assertEqual("remote-governance-unavailable\n", output.getvalue())

    def test_cli_fetches_full_detail_for_only_the_eligible_tag_ruleset(self) -> None:
        unrelated = {
            "id": 99,
            "name": "Other release tags",
            "enforcement": "active",
        }
        payloads = (protected_branch(), main_protection(), [unrelated, v2_tag_ruleset_summary()], v2_tag_ruleset())
        output = io.StringIO()
        with patch.object(self.cli, "_load_governance_module", return_value=self.governance), patch.object(
            self.governance, "fetch_json", side_effect=payloads
        ) as fetch_json, redirect_stdout(output):
            code = self.cli.main(["--repo", "eric861129/Workflow-skill-router"])

        self.assertEqual(0, code)
        self.assertEqual("PASS: remote release governance matches contract\n", output.getvalue())
        self.assertEqual(
            [
                "repos/eric861129/Workflow-skill-router/branches/main",
                "repos/eric861129/Workflow-skill-router/branches/main/protection",
                "repos/eric861129/Workflow-skill-router/rulesets?targets=tag&per_page=100&page=1",
                "repos/eric861129/Workflow-skill-router/rulesets/42",
            ],
            [call.args[1] for call in fetch_json.call_args_list],
        )

    def test_cli_flattens_later_ruleset_pages_before_fetching_detail(self) -> None:
        first_page = [
            {"id": index, "name": f"Other tag ruleset {index}", "enforcement": "active"}
            for index in range(1, 101)
        ]
        payloads = (protected_branch(), main_protection(), first_page, [v2_tag_ruleset_summary()], v2_tag_ruleset())
        output = io.StringIO()
        with patch.object(self.cli, "_load_governance_module", return_value=self.governance), patch.object(
            self.governance, "fetch_json", side_effect=payloads
        ) as fetch_json, redirect_stdout(output):
            code = self.cli.main(["--repo", "eric861129/Workflow-skill-router"])

        self.assertEqual(0, code)
        self.assertEqual("PASS: remote release governance matches contract\n", output.getvalue())
        self.assertEqual(
            [
                "repos/eric861129/Workflow-skill-router/branches/main",
                "repos/eric861129/Workflow-skill-router/branches/main/protection",
                "repos/eric861129/Workflow-skill-router/rulesets?targets=tag&per_page=100&page=1",
                "repos/eric861129/Workflow-skill-router/rulesets?targets=tag&per_page=100&page=2",
                "repos/eric861129/Workflow-skill-router/rulesets/42",
            ],
            [call.args[1] for call in fetch_json.call_args_list],
        )

    def test_cli_returns_public_safe_failure_for_malformed_ruleset_page(self) -> None:
        first_page = [
            {"id": index, "name": f"Other tag ruleset {index}", "enforcement": "active"}
            for index in range(1, 101)
        ]
        output = io.StringIO()
        with patch.object(self.cli, "_load_governance_module", return_value=self.governance), patch.object(
            self.governance, "fetch_json", side_effect=(protected_branch(), main_protection(), first_page, {"invalid": True})
        ), redirect_stdout(output):
            code = self.cli.main(["--repo", "eric861129/Workflow-skill-router"])

        self.assertEqual(1, code)
        self.assertEqual("remote-governance-unavailable\n", output.getvalue())

    def test_cli_returns_public_safe_failure_for_detail_fetch_failures_or_malformed_detail(self) -> None:
        malformed_detail = v2_tag_ruleset()
        malformed_detail["conditions"] = {"ref_name": {"include": "refs/tags/v2.*"}}
        cases = (
            (self.governance.RemoteGovernanceUnavailableError("remote-governance-unavailable"),),
            ("not-a-ruleset",),
            (malformed_detail,),
        )
        for detail in cases:
            with self.subTest(detail=detail):
                output = io.StringIO()
                with patch.object(self.cli, "_load_governance_module", return_value=self.governance), patch.object(
                    self.governance,
                    "fetch_json",
                    side_effect=(protected_branch(), main_protection(), [v2_tag_ruleset_summary()], *detail),
                ), redirect_stdout(output):
                    code = self.cli.main(["--repo", "eric861129/Workflow-skill-router"])
                self.assertEqual(1, code)
                self.assertEqual("remote-governance-unavailable\n", output.getvalue())

    def test_fetch_json_uses_no_mutation_flags_or_request_body(self) -> None:
        completed = subprocess.CompletedProcess(["gh"], 0, stdout="{}", stderr="")
        with patch.object(self.governance.subprocess, "run", return_value=completed) as run:
            self.assertEqual({}, self.governance.fetch_json("owner/repo", "repos/owner/repo/rulesets/42"))

        command = run.call_args.args[0]
        options = run.call_args.kwargs
        self.assertEqual(["gh", "api", "repos/owner/repo/rulesets/42"], command)
        self.assertNotIn("--method", command)
        self.assertNotIn("--raw-field", command)
        self.assertNotIn("input", options)


if __name__ == "__main__":
    unittest.main()
