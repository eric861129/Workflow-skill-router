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
    def test_plugin_lockfile_excludes_the_known_vulnerable_fast_uri_range(self) -> None:
        lockfile = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        fast_uri = lockfile["packages"]["node_modules/fast-uri"]["version"]

        self.assertGreaterEqual(version_tuple(fast_uri), (3, 1, 4))

    def test_temporary_mcp_sdk_dependency_exception_has_an_expiry_path(self) -> None:
        risk_register = RISK_REGISTER.read_text(encoding="utf-8")

        for required in (
            "@modelcontextprotocol/sdk",
            "@hono/node-server",
            "No HTTP listener or",
            "static-file middleware is started by the Plugin runtime.",
            "Exit criterion",
            "2.0.5",
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
