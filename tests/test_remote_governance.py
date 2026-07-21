from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "remote_governance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("remote_governance", MODULE_PATH)
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


class RemoteGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.governance = load_module()

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


if __name__ == "__main__":
    unittest.main()
