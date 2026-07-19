import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class CommunityHealthV2Tests(unittest.TestCase):
    def test_security_policy_covers_the_v2_local_attack_surface(self) -> None:
        policy = read("SECURITY.md").lower()
        for required in (
            "mcp server",
            "sqlite",
            "plugin runtime",
            "private vulnerability reporting",
            "acknowledge",
            "business days",
            "remediation",
        ):
            with self.subTest(required=required):
                self.assertIn(required, policy)

    def test_contributing_has_distinct_v2_paths(self) -> None:
        guide = read("CONTRIBUTING.md").lower()
        for required in (
            "router core",
            "mcp",
            "model evaluation",
            "documentation site",
            "documentation-only",
            "no live model",
        ):
            with self.subTest(required=required):
                self.assertIn(required, guide)

    def test_governance_support_and_maintainer_contracts_exist(self) -> None:
        governance = read("GOVERNANCE.md").lower()
        support = read("SUPPORT.md").lower()
        maintainers = read("MAINTAINERS.md").lower()

        for required in ("maintainer", "decision", "release authority", "conflict"):
            self.assertIn(required, governance)
        self.assertIn("github discussions", support)
        self.assertIn("private vulnerability reporting", support)
        self.assertNotIn("public issue for a vulnerability", support)
        self.assertIn("release", maintainers)
        self.assertIn("security", maintainers)

    def test_v2_issue_forms_collect_reproducible_sanitized_evidence(self) -> None:
        runtime_bug = read(".github/ISSUE_TEMPLATE/plugin-runtime-bug.yml").lower()
        evaluation = read(".github/ISSUE_TEMPLATE/evaluation-case.yml").lower()
        routing = read(".github/ISSUE_TEMPLATE/routing-failure.yml").lower()

        for required in (
            "operating system",
            "codex version",
            "plugin version",
            "python version",
            "node.js version",
            "install mode",
            "sanitized logs",
            "reproduction",
        ):
            self.assertIn(required, runtime_bug)

        for required in (
            "evaluation profile",
            "adapter kind",
            "attempt count",
            "manifest digests",
            "evidence status",
            "no secrets",
        ):
            self.assertIn(required, evaluation)

        for required in ("task size", "user-specified skill", "consent"):
            self.assertIn(required, routing)

    def test_pull_request_and_release_templates_are_v2_release_aware(self) -> None:
        pull_request = read(".github/PULL_REQUEST_TEMPLATE.md").lower()
        release = read(".github/RELEASE_TEMPLATE.md").lower()

        for required in ("router core", "plugin / mcp", "evaluation", "skill-only"):
            self.assertIn(required, pull_request)
        for required in ("v2.*", "sbom", "provenance", "attestation", "quota"):
            self.assertIn(required, release)


if __name__ == "__main__":
    unittest.main()
