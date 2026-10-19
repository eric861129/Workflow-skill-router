import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = ROOT / "plugins" / "workflow-skill-router" / "package-lock.json"
RISK_REGISTER = ROOT / "docs" / "governance" / "plugin-dependency-risk.md"
ENGLISH_SECURITY_DOC = ROOT / "site" / "src" / "content" / "docs" / "reference" / "security-boundaries.md"
TRADITIONAL_CHINESE_SECURITY_DOC = ROOT / "site" / "src" / "content" / "docs" / "zh-tw" / "reference" / "security-boundaries.md"
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Unsupported semantic version: {value}")
    return tuple(int(part) for part in match.groups())


class PluginDependencySecurityTests(unittest.TestCase):
    def test_plugin_lockfile_excludes_reviewed_vulnerable_dependency_ranges(self) -> None:
        lockfile = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        minimum_versions = {
            "@modelcontextprotocol/sdk": (1, 32, 1),
            "@hono/node-server": (2, 1, 5),
            "fast-uri": (3, 1, 8),
            "proxy-addr": (2, 0, 8),
            "hono": (4, 13, 13),
            "ip-address": (10, 7, 4),
            "qs": (6, 16, 1),
        }
        for name, minimum in minimum_versions.items():
            with self.subTest(package=name):
                version = lockfile["packages"][f"node_modules/{name}"]["version"]
                self.assertGreaterEqual(version_tuple(version), minimum)

    def test_dependency_decision_records_resolved_exception_and_release_gate(self) -> None:
        risk_register = RISK_REGISTER.read_text(encoding="utf-8")

        for required in (
            "@modelcontextprotocol/sdk",
            "@hono/node-server",
            "No HTTP listener or",
            "static-file middleware is started by the Plugin runtime.",
            "zero findings",
            "no active dependency exception",
            "npm audit --omit=dev",
            "2026-10-19",
        ):
            with self.subTest(required=required):
                self.assertIn(required, risk_register)

    def test_public_security_docs_link_the_dependency_decision(self) -> None:
        self.assertIn(
            "Plugin dependency security decision",
            ENGLISH_SECURITY_DOC.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Plugin 相依套件安全決策",
            TRADITIONAL_CHINESE_SECURITY_DOC.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
