from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "verify-plugin-distribution-governance.py"
CONTRACT_PATH = ROOT / ".github" / "plugin-distribution-governance.json"
REPOSITORY = "eric861129/workflow-skill-router-plugin"
RELEASE_APP = {
    "actor_id": 4361147,
    "actor_type": "Integration",
    "bypass_mode": "always",
}


def load_verifier(test_case: unittest.TestCase):
    test_case.assertTrue(
        SCRIPT_PATH.is_file(),
        "plugin distribution governance verifier is required",
    )
    specification = importlib.util.spec_from_file_location(
        "workflow_skill_router_plugin_distribution_governance",
        SCRIPT_PATH,
    )
    test_case.assertIsNotNone(specification)
    test_case.assertIsNotNone(specification.loader)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def repository_payload() -> dict[str, object]:
    return {
        "default_branch": "main",
        "private": False,
        "visibility": "public",
    }


def branch_payload() -> dict[str, object]:
    return {"name": "main", "protected": True}


def branch_ruleset() -> dict[str, object]:
    return {
        "id": 101,
        "name": "Protected generated main",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "exclude": [],
                "include": ["refs/heads/main"],
            }
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {
                            "context": "scan",
                            "integration_id": 15368,
                        }
                    ],
                    "strict_required_status_checks_policy": True,
                },
            },
        ],
        "bypass_actors": [deepcopy(RELEASE_APP)],
    }


def tag_ruleset() -> dict[str, object]:
    return {
        "id": 202,
        "name": "Immutable Plugin release tags",
        "target": "tag",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "exclude": [],
                "include": ["refs/tags/v*"],
            }
        },
        "rules": [
            {"type": "creation"},
            {"type": "update"},
            {"type": "deletion"},
        ],
        "bypass_actors": [deepcopy(RELEASE_APP)],
    }


def ruleset_summary(ruleset: dict[str, object]) -> dict[str, object]:
    return {
        "id": ruleset["id"],
        "name": ruleset["name"],
        "enforcement": ruleset["enforcement"],
    }


def response_map(
    *,
    repository: dict[str, object] | None = None,
    branch: dict[str, object] | None = None,
    branch_rule: dict[str, object] | None = None,
    tag_rule: dict[str, object] | None = None,
) -> dict[str, object]:
    effective_branch_rule = branch_rule or branch_ruleset()
    effective_tag_rule = tag_rule or tag_ruleset()
    return {
        f"repos/{REPOSITORY}": repository or repository_payload(),
        f"repos/{REPOSITORY}/branches/main": branch or branch_payload(),
        (
            f"repos/{REPOSITORY}/rulesets"
            "?targets=branch&per_page=100&page=1"
        ): [ruleset_summary(effective_branch_rule)],
        f"repos/{REPOSITORY}/rulesets/{effective_branch_rule['id']}": (
            effective_branch_rule
        ),
        (
            f"repos/{REPOSITORY}/rulesets"
            "?targets=tag&per_page=100&page=1"
        ): [ruleset_summary(effective_tag_rule)],
        f"repos/{REPOSITORY}/rulesets/{effective_tag_rule['id']}": effective_tag_rule,
    }


class PluginDistributionGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = load_verifier(self)

    def run_cli(
        self,
        responses: dict[str, object],
    ) -> tuple[int, str, list[str]]:
        requested: list[str] = []

        def fake_fetch(repo: str, endpoint: str) -> object:
            self.assertEqual(REPOSITORY, repo)
            requested.append(endpoint)
            try:
                return deepcopy(responses[endpoint])
            except KeyError as error:
                raise AssertionError(f"unexpected endpoint: {endpoint}") from error

        output = io.StringIO()
        with patch.object(self.verifier, "fetch_json", side_effect=fake_fetch):
            with redirect_stdout(output):
                result = self.verifier.main(
                    ["--contract", str(CONTRACT_PATH)]
                )
        return result, output.getvalue(), requested

    def test_complete_public_target_governance_passes_with_get_only_reads(
        self,
    ) -> None:
        result, output, requested = self.run_cli(response_map())

        self.assertEqual(0, result)
        self.assertIn("PASS", output)
        self.assertEqual(
            [
                f"repos/{REPOSITORY}",
                f"repos/{REPOSITORY}/branches/main",
                (
                    f"repos/{REPOSITORY}/rulesets"
                    "?targets=branch&per_page=100&page=1"
                ),
                f"repos/{REPOSITORY}/rulesets/101",
                (
                    f"repos/{REPOSITORY}/rulesets"
                    "?targets=tag&per_page=100&page=1"
                ),
                f"repos/{REPOSITORY}/rulesets/202",
            ],
            requested,
        )

    def test_non_public_repository_is_rejected(self) -> None:
        repository = repository_payload()
        repository["private"] = True
        repository["visibility"] = "private"

        result, output, _ = self.run_cli(response_map(repository=repository))

        self.assertEqual(1, result)
        self.assertIn("repository-not-public", output)

    def test_wrong_default_branch_is_rejected(self) -> None:
        repository = repository_payload()
        repository["default_branch"] = "develop"

        result, output, _ = self.run_cli(response_map(repository=repository))

        self.assertEqual(1, result)
        self.assertIn("default-branch-mismatch", output)

    def test_unprotected_target_branch_is_rejected(self) -> None:
        result, output, _ = self.run_cli(
            response_map(branch={"name": "main", "protected": False})
        )

        self.assertEqual(1, result)
        self.assertIn("target-branch-not-protected", output)

    def test_missing_scanner_requirement_is_rejected(self) -> None:
        branch_rule = branch_ruleset()
        branch_rule["rules"] = [
            rule
            for rule in branch_rule["rules"]  # type: ignore[index]
            if rule["type"] != "required_status_checks"
        ]

        result, output, _ = self.run_cli(
            response_map(branch_rule=branch_rule)
        )

        self.assertEqual(1, result)
        self.assertIn("scanner-requirement-missing", output)

    def test_missing_target_branch_protection_rules_are_rejected(self) -> None:
        branch_rule = branch_ruleset()
        branch_rule["rules"] = [
            rule
            for rule in branch_rule["rules"]  # type: ignore[index]
            if rule["type"] != "non_fast_forward"
        ]

        result, output, _ = self.run_cli(
            response_map(branch_rule=branch_rule)
        )

        self.assertEqual(1, result)
        self.assertIn("target-branch-rules-missing", output)

    def test_missing_refs_tags_v_star_protection_is_rejected(self) -> None:
        tag_rule = tag_ruleset()
        tag_rule["conditions"] = {
            "ref_name": {
                "exclude": [],
                "include": ["refs/tags/v2.*"],
            }
        }

        result, output, _ = self.run_cli(response_map(tag_rule=tag_rule))

        self.assertEqual(1, result)
        self.assertIn("tag-protection-missing", output)

    def test_missing_release_app_bypass_is_rejected_for_branch_or_tag(
        self,
    ) -> None:
        for target in ("branch", "tag"):
            with self.subTest(target=target):
                branch_rule = branch_ruleset()
                tag_rule = tag_ruleset()
                if target == "branch":
                    branch_rule["bypass_actors"] = []
                else:
                    tag_rule["bypass_actors"] = []

                result, output, _ = self.run_cli(
                    response_map(
                        branch_rule=branch_rule,
                        tag_rule=tag_rule,
                    )
                )

                self.assertEqual(1, result)
                self.assertIn("release-app-bypass-missing", output)

    def test_split_branch_rulesets_cannot_collectively_satisfy_contract(
        self,
    ) -> None:
        branch_controls = branch_ruleset()
        branch_controls["rules"] = [
            rule
            for rule in branch_controls["rules"]  # type: ignore[index]
            if rule["type"] != "required_status_checks"
        ]
        scanner_only = branch_ruleset()
        scanner_only["id"] = 102
        scanner_only["rules"] = [
            rule
            for rule in scanner_only["rules"]  # type: ignore[index]
            if rule["type"] == "required_status_checks"
        ]

        violations = self.verifier.evaluate_governance(
            self.verifier.load_contract(CONTRACT_PATH),
            repository_payload(),
            branch_payload(),
            [branch_controls, scanner_only],
            [tag_ruleset()],
        )

        self.assertIn("scanner-requirement-missing", violations)

    def test_split_tag_rulesets_cannot_collectively_satisfy_contract(
        self,
    ) -> None:
        tag_controls = tag_ruleset()
        tag_controls["bypass_actors"] = []
        bypass_only = tag_ruleset()
        bypass_only["id"] = 203
        bypass_only["rules"] = []

        violations = self.verifier.evaluate_governance(
            self.verifier.load_contract(CONTRACT_PATH),
            repository_payload(),
            branch_payload(),
            [branch_ruleset()],
            [tag_controls, bypass_only],
        )

        self.assertIn("release-app-bypass-missing", violations)

    def test_ruleset_excluding_its_included_target_ref_is_rejected(
        self,
    ) -> None:
        cases = (
            (
                "branch",
                branch_ruleset(),
                "refs/heads/main",
                "target-branch-rules-missing",
            ),
            ("tag", tag_ruleset(), "refs/tags/v*", "tag-protection-missing"),
        )
        for target, excluded_ruleset, excluded_ref, expected in cases:
            with self.subTest(target=target):
                excluded_ruleset["conditions"]["ref_name"]["exclude"] = [  # type: ignore[index]
                    excluded_ref
                ]
                branch_rules = (
                    [excluded_ruleset]
                    if target == "branch"
                    else [branch_ruleset()]
                )
                tag_rules = (
                    [excluded_ruleset]
                    if target == "tag"
                    else [tag_ruleset()]
                )

                violations = self.verifier.evaluate_governance(
                    self.verifier.load_contract(CONTRACT_PATH),
                    repository_payload(),
                    branch_payload(),
                    branch_rules,
                    tag_rules,
                )

                self.assertIn(expected, violations)

    def test_fetch_json_explicitly_uses_get_without_request_body(self) -> None:
        with patch.object(
            self.verifier.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="{}",
                stderr="",
            ),
        ) as run:
            self.verifier.fetch_json(REPOSITORY, f"repos/{REPOSITORY}")

        command = run.call_args.args[0]
        self.assertEqual(
            ["gh", "api", "--method", "GET", f"repos/{REPOSITORY}"],
            command,
        )
        self.assertFalse(
            any(
                argument in command
                for argument in (
                    "--field",
                    "-f",
                    "--input",
                    "--raw-field",
                    "-F",
                    "--method=DELETE",
                    "--method=PATCH",
                    "--method=POST",
                    "--method=PUT",
                )
            )
        )

    def test_checked_in_contract_and_docs_define_canonical_ownership(
        self,
    ) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(REPOSITORY, contract["repository"])
        self.assertEqual("public", contract["visibility"])
        self.assertEqual("main", contract["default_branch"])
        self.assertEqual("scan", contract["scanner"]["required_check"]["context"])
        self.assertEqual(
            "refs/tags/v*",
            contract["tag_ruleset"]["ref_name_include"],
        )
        self.assertEqual(
            RELEASE_APP,
            contract["release_app_bypass"],
        )

        generated_readme = (
            ROOT / "release" / "plugin-distribution" / "README.md.tmpl"
        ).read_text(encoding="utf-8")
        self.assertIn("GENERATED DISTRIBUTION", generated_readme)
        self.assertIn("Do not manually repair", generated_readme)
        self.assertIn(
            "https://github.com/eric861129/Workflow-skill-router",
            generated_readme,
        )

        bilingual_docs = (
            (
                ROOT
                / "site"
                / "src"
                / "content"
                / "docs"
                / "contributing"
                / "release-process.md"
            ).read_text(encoding="utf-8"),
            (
                ROOT
                / "site"
                / "src"
                / "content"
                / "docs"
                / "zh-tw"
                / "contributing"
                / "release-process.md"
            ).read_text(encoding="utf-8"),
        )
        for text, repair_term in zip(
            bilingual_docs,
            ("manual", "手動"),
            strict=True,
        ):
            self.assertIn("canonical", text.lower())
            self.assertIn("Scanner", text)
            self.assertIn("tag", text)
            self.assertIn(repair_term, text)


if __name__ == "__main__":
    unittest.main()
