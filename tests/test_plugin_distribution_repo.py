from __future__ import annotations

import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build-plugin-distribution-repo.py"
VERSION = "2.0.1"
SOURCE_REVISION = "a" * 40
TARGET_REPOSITORY = "https://github.com/eric861129/workflow-skill-router-plugin"


def load_builder(test_case: unittest.TestCase):
    test_case.assertTrue(
        BUILDER_PATH.is_file(),
        "plugin distribution builder module is required",
    )
    specification = importlib.util.spec_from_file_location(
        "workflow_skill_router_plugin_distribution_builder",
        BUILDER_PATH,
    )
    test_case.assertIsNotNone(specification)
    test_case.assertIsNotNone(specification.loader)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


class PluginDistributionRepoTests(unittest.TestCase):
    def test_two_builds_from_the_same_inputs_are_byte_identical(self) -> None:
        builder = load_builder(self)

        first = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )
        second = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )

        self.assertEqual(first.version, VERSION)
        self.assertEqual(first.source_revision, SOURCE_REVISION)
        self.assertEqual(first.files, second.files)
        self.assertTrue(first.files)
        self.assertTrue(
            all(isinstance(path, PurePosixPath) for path in first.files)
        )

    def test_unsafe_allowlist_path_fails_closed(self) -> None:
        builder = load_builder(self)
        with tempfile.TemporaryDirectory() as directory:
            allowlist_path = Path(directory) / "unsafe.json"
            allowlist_path.write_text(
                json.dumps({"files": ["../outside.txt"]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, r"(?i)(unsafe|allowlist)"):
                builder.build_distribution_tree(
                    ROOT,
                    version=VERSION,
                    source_revision=SOURCE_REVISION,
                    allowlist_path=allowlist_path,
                )

    def test_target_metadata_and_packaging_files_are_canonical(self) -> None:
        builder = load_builder(self)
        tree = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )

        manifest = json.loads(
            tree.files[PurePosixPath(".codex-plugin/plugin.json")]
        )
        self.assertEqual(manifest["repository"], TARGET_REPOSITORY)
        self.assertEqual(manifest["interface"]["composerIcon"], "./assets/icon.svg")
        self.assertEqual(manifest["interface"]["logo"], "./assets/icon.svg")

        package = json.loads(tree.files[PurePosixPath("package.json")])
        self.assertEqual(package["name"], "workflow-skill-router-plugin")
        self.assertEqual(package["repository"]["url"], f"{TARGET_REPOSITORY}.git")
        self.assertNotIn("directory", package["repository"])
        self.assertEqual(package["bugs"]["url"], f"{TARGET_REPOSITORY}/issues")

        package_lock = json.loads(tree.files[PurePosixPath("package-lock.json")])
        self.assertEqual(package_lock["name"], "workflow-skill-router-plugin")
        self.assertEqual(
            package_lock["packages"][""]["name"],
            "workflow-skill-router-plugin",
        )

        release_metadata = json.loads(tree.files[PurePosixPath("release.json")])
        self.assertEqual(
            release_metadata,
            {
                "canonical_repository": (
                    "https://github.com/eric861129/Workflow-skill-router"
                ),
                "channel": "latest",
                "source_revision": SOURCE_REVISION,
                "target_repository": TARGET_REPOSITORY,
                "version": VERSION,
            },
        )

        packaging_files = {
            PurePosixPath(".codexignore"),
            PurePosixPath(".github/dependabot.yml"),
            PurePosixPath(".github/workflows/hol-plugin-scanner.yml"),
            PurePosixPath(".gitignore"),
            PurePosixPath("PRIVACY.md"),
            PurePosixPath("README.md"),
            PurePosixPath("SECURITY.md"),
            PurePosixPath("TERMS.md"),
            PurePosixPath("UPSTREAM.md"),
            PurePosixPath("assets/icon.svg"),
        }
        self.assertTrue(packaging_files.issubset(tree.files))
        for path in (
            PurePosixPath("README.md"),
            PurePosixPath("UPSTREAM.md"),
        ):
            text = tree.files[path].decode("utf-8")
            self.assertIn(VERSION, text)
            self.assertIn(SOURCE_REVISION, text)
            self.assertNotIn("{{", text)
            self.assertNotIn("}}", text)

        for path in (
            PurePosixPath(".codex-plugin/plugin.json"),
            PurePosixPath("package-lock.json"),
            PurePosixPath("package.json"),
            PurePosixPath("release.json"),
        ):
            value = json.loads(tree.files[path])
            expected = (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            self.assertEqual(tree.files[path], expected)

        scanner = tree.files[
            PurePosixPath(".github/workflows/hol-plugin-scanner.yml")
        ].decode("utf-8")
        self.assertRegex(
            scanner,
            r"hashgraph-online/ai-plugin-scanner-action@[0-9a-f]{40}",
        )
        self.assertIn("min_score: 80", scanner)
        self.assertIn("fail_on_severity: high", scanner)

    def test_allowlist_is_sorted_unique_and_every_output_path_is_safe(self) -> None:
        builder = load_builder(self)
        allowlist = json.loads(
            (
                ROOT
                / "release"
                / "allowlists"
                / "plugin-distribution-repository-files.json"
            ).read_text(encoding="utf-8")
        )["files"]
        self.assertEqual(allowlist, sorted(set(allowlist)))

        tree = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )
        for path in tree.files:
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertEqual(path.as_posix(), str(path))

    def test_existing_unexpected_output_fails_without_deleting_it(self) -> None:
        builder = load_builder(self)
        tree = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plugin-repository"
            output.mkdir()
            sentinel = output / "do-not-delete.txt"
            sentinel.write_text("preserve me\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"(?i)unexpected"):
                builder.write_distribution_tree(tree, output)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve me\n")
            self.assertEqual(list(output.iterdir()), [sentinel])

    def test_invalid_version_and_revision_fail_before_reading_sources(self) -> None:
        builder = load_builder(self)

        with self.assertRaisesRegex(ValueError, r"(?i)GA version"):
            builder.build_distribution_tree(
                ROOT,
                version="2.0.1-beta.1",
                source_revision=SOURCE_REVISION,
            )
        with self.assertRaisesRegex(ValueError, r"(?i)40-character"):
            builder.build_distribution_tree(
                ROOT,
                version=VERSION,
                source_revision="abc123",
            )


if __name__ == "__main__":
    unittest.main()
