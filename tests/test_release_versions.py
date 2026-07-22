import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GA_VERSION = "2.0.0"
GA_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class ReleaseVersionContractTests(unittest.TestCase):
    def test_release_metadata_declares_the_current_ga_version(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )

        self.assertEqual(EXPECTED_GA_VERSION, release["v2_version"])
        self.assertRegex(release["v2_version"], GA_VERSION_PATTERN)

    def test_product_version_surfaces_match_current_release_metadata(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        core_project = tomllib.loads(
            (ROOT / "packages" / "router-core" / "pyproject.toml").read_text(
                encoding="utf-8"
            )
        )
        core_init = (
            ROOT
            / "packages"
            / "router-core"
            / "src"
            / "workflow_skill_router"
            / "__init__.py"
        ).read_text(encoding="utf-8")
        plugin_package = json.loads(
            (
                ROOT / "plugins" / "workflow-skill-router" / "package.json"
            ).read_text(encoding="utf-8")
        )
        plugin_lock = json.loads(
            (
                ROOT / "plugins" / "workflow-skill-router" / "package-lock.json"
            ).read_text(encoding="utf-8")
        )
        server_source = (
            ROOT
            / "plugins"
            / "workflow-skill-router"
            / "mcp"
            / "src"
            / "server.ts"
        ).read_text(encoding="utf-8")

        core_init_match = re.search(
            r'^__version__\s*=\s*"(?P<version>[^"]+)"$',
            core_init,
            flags=re.MULTILINE,
        )
        server_version_match = re.search(
            r'new McpServer\(\{ name: "workflow-skill-router", version: "(?P<version>[^"]+)" \}\)',
            server_source,
        )
        self.assertIsNotNone(core_init_match)
        self.assertIsNotNone(server_version_match)

        expected_version = release["v2_version"]
        version_surfaces = {
            "Router Core pyproject": core_project["project"]["version"],
            "Router Core package": core_init_match["version"],
            "Plugin package": plugin_package["version"],
            "Plugin lockfile": plugin_lock["version"],
            "Plugin lockfile root package": plugin_lock["packages"][""]["version"],
            "MCP server": server_version_match["version"],
        }

        for surface, version in version_surfaces.items():
            with self.subTest(surface=surface):
                self.assertEqual(expected_version, version)
                self.assertRegex(version, GA_VERSION_PATTERN)


if __name__ == "__main__":
    unittest.main()
