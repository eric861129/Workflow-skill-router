import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GA_VERSION = "2.0.0"
GA_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
MCP_SERVER_VERSION_DECLARATION = re.compile(
    r'^(?:export\s+)?(?:const|var)\s+MCP_SERVER_VERSION\s*=\s*"(?P<version>[^"]+)"\s*;$',
    flags=re.MULTILINE,
)


def executable_mcp_server_versions(source: str) -> list[str]:
    uncommented_lines: list[str] = []
    in_block_comment = False

    for raw_line in source.splitlines():
        line = raw_line
        if in_block_comment:
            block_end = line.find("*/")
            if block_end == -1:
                continue
            line = line[block_end + 2 :]
            in_block_comment = False

        while True:
            block_start = line.find("/*")
            line_comment = line.find("//")
            if line_comment != -1 and (
                block_start == -1 or line_comment < block_start
            ):
                line = line[:line_comment]
                break
            if block_start == -1:
                break

            block_end = line.find("*/", block_start + 2)
            if block_end == -1:
                line = line[:block_start]
                in_block_comment = True
                break
            line = line[:block_start] + line[block_end + 2 :]

        uncommented_lines.append(line)

    return [
        match["version"]
        for match in MCP_SERVER_VERSION_DECLARATION.finditer(
            "\n".join(uncommented_lines)
        )
    ]


class ReleaseVersionContractTests(unittest.TestCase):
    def test_release_metadata_declares_the_current_ga_version(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )

        self.assertEqual(EXPECTED_GA_VERSION, release["v2_version"])
        self.assertRegex(release["v2_version"], GA_VERSION_PATTERN)

    def test_ga_version_pattern_rejects_leading_zeroes_and_suffixes(self) -> None:
        for invalid_version in (
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-beta.1",
            "1.2.3+build.1",
        ):
            with self.subTest(version=invalid_version):
                self.assertIsNone(GA_VERSION_PATTERN.fullmatch(invalid_version))

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
        core_init_match = re.search(
            r'^__version__\s*=\s*"(?P<version>[^"]+)"$',
            core_init,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(core_init_match)

        expected_version = release["v2_version"]
        version_surfaces = {
            "Router Core pyproject": core_project["project"]["version"],
            "Router Core package": core_init_match["version"],
            "Plugin package": plugin_package["version"],
            "Plugin lockfile": plugin_lock["version"],
            "Plugin lockfile root package": plugin_lock["packages"][""]["version"],
        }

        for surface, version in version_surfaces.items():
            with self.subTest(surface=surface):
                self.assertRegex(version, GA_VERSION_PATTERN)
                self.assertEqual(expected_version, version)

    def test_mcp_entrypoints_match_current_release_metadata(self) -> None:
        release = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )
        entrypoints = {
            "MCP source": ROOT
            / "plugins"
            / "workflow-skill-router"
            / "mcp"
            / "src"
            / "server.ts",
            "MCP bundle": ROOT
            / "plugins"
            / "workflow-skill-router"
            / "mcp"
            / "server.bundle.mjs",
        }

        for entrypoint, path in entrypoints.items():
            versions = executable_mcp_server_versions(path.read_text(encoding="utf-8"))
            with self.subTest(entrypoint=entrypoint):
                self.assertEqual(1, len(versions), entrypoint)
                if len(versions) == 1:
                    self.assertRegex(versions[0], GA_VERSION_PATTERN)
                    self.assertEqual(release["v2_version"], versions[0])

    def test_mcp_version_extraction_ignores_commented_declarations(self) -> None:
        source = '''
// export const MCP_SERVER_VERSION = "1.0.0";
/*
var MCP_SERVER_VERSION = "1.1.0";
*/
export const MCP_SERVER_VERSION = "2.0.0";
'''

        self.assertEqual(["2.0.0"], executable_mcp_server_versions(source))


if __name__ == "__main__":
    unittest.main()
