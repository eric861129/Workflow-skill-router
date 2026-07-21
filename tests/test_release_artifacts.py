import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-release-artifacts.py"


class ReleaseArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "release"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(BUILDER),
                "--output-dir",
                str(cls.output),
                "--provenance-mode",
                "test",
                "--check-determinism",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.version = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )["v2_version"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_channels_do_not_promote_the_v2_prerelease(self) -> None:
        latest = json.loads(
            (self.output / "channels" / "latest.json").read_text(encoding="utf-8")
        )
        latest_v2 = json.loads(
            (self.output / "channels" / "latest-v2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("1.3.1", latest["version"])
        self.assertEqual(self.version, latest_v2["version"])

    def test_skill_archive_is_safe_sorted_and_matches_canonical_source(self) -> None:
        archive_path = (
            self.output / f"workflow-skill-router-skill-v{self.version}.zip"
        )
        with ZipFile(archive_path) as archive:
            names = archive.namelist()
            self.assertEqual(sorted(names), names)
            self.assertTrue(
                all(
                    not name.startswith("/") and ".." not in Path(name).parts
                    for name in names
                )
            )
            self.assertEqual(
                (ROOT / "starter/v2/workflow-skill-router/SKILL.md").read_bytes(),
                archive.read("workflow-skill-router/SKILL.md"),
            )

    def test_plugin_archive_contains_only_existing_runtime_allowlist_files(self) -> None:
        allowlist = json.loads(
            (
                ROOT / "release" / "allowlists" / "plugin-runtime-files.json"
            ).read_text(encoding="utf-8")
        )["files"]
        plugin_root = ROOT / "plugins" / "workflow-skill-router"
        expected = {
            f"workflow-skill-router/{path}"
            for path in allowlist
            if (plugin_root / path).is_file()
        }

        archive_path = (
            self.output / f"workflow-skill-router-plugin-v{self.version}.zip"
        )
        with ZipFile(archive_path) as archive:
            names = set(archive.namelist())

        self.assertEqual(expected, names)
        self.assertTrue(all("__pycache__" not in Path(name).parts for name in names))
        self.assertTrue(all("/mcp/src/" not in name for name in names))
        self.assertTrue(all("/mcp/test/" not in name for name in names))
        self.assertTrue(all("/scripts/" not in name for name in names))

    def test_sbom_and_provenance_describe_real_runtime_dependencies(self) -> None:
        sbom = json.loads(
            (
                self.output
                / "sbom"
                / f"workflow-skill-router-v{self.version}.spdx.json"
            ).read_text(encoding="utf-8")
        )
        packages = {package["name"]: package for package in sbom["packages"]}
        self.assertEqual("1.29.0", packages["@modelcontextprotocol/sdk"]["versionInfo"])
        self.assertEqual("4.1.12", packages["zod"]["versionInfo"])
        self.assertEqual("BUILD_TOOL", packages["esbuild"]["primaryPackagePurpose"])

        provenance = json.loads(
            (
                self.output
                / "provenance"
                / f"workflow-skill-router-v{self.version}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(provenance["publishable"])
        self.assertIsNone(provenance["source_revision"])
        self.assertIsNone(provenance["source_tree"])
        self.assertEqual(
            "workflow-skill-router-v2-release-builder", provenance["builder"]
        )

    def test_checksums_cover_every_release_asset_except_the_checksum_file(self) -> None:
        rows = {}
        for line in (self.output / "checksums.sha256").read_text(
            encoding="utf-8"
        ).splitlines():
            digest, relative = line.split("  ", 1)
            rows[relative] = digest

        expected = {
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file() and path.name != "checksums.sha256"
        }
        self.assertEqual(expected, set(rows))
        for relative, digest in rows.items():
            self.assertEqual(
                digest,
                sha256((self.output / relative).read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
