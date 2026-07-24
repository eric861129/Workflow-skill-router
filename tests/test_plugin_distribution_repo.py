from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build-plugin-distribution-repo.py"
SYNCHRONIZER_PATH = ROOT / "scripts" / "sync-plugin-distribution-repo.py"
VERSION = "2.0.1"
SOURCE_REVISION = "a" * 40
TARGET_REPOSITORY = "https://github.com/eric861129/workflow-skill-router-plugin"
EXPECTED_REMOTE = "eric861129/workflow-skill-router-plugin"
OWNERSHIP_FILENAME = ".workflow-skill-router-distribution.json"


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


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *arguments),
        cwd=repository,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def create_generated_root(
    parent: Path,
    files: dict[str, str],
    *,
    version: str = VERSION,
    source_revision: str = SOURCE_REVISION,
) -> Path:
    generated_root = parent / "generated"
    generated_root.mkdir()
    for relative_name, content in files.items():
        target = generated_root / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    write_json(
        generated_root / "release.json",
        {
            "source_revision": source_revision,
            "version": version,
        },
    )
    return generated_root


def create_target_repository(
    parent: Path,
    files: dict[str, str],
    *,
    remote: str = TARGET_REPOSITORY,
) -> Path:
    target_root = parent / "target"
    target_root.mkdir()
    initialized = run_git(target_root, "init")
    if initialized.returncode != 0:
        raise AssertionError(initialized.stderr)
    for key, value in (
        ("user.name", "Workflow Skill Router Tests"),
        ("user.email", "workflow-skill-router@example.invalid"),
        ("core.autocrlf", "false"),
    ):
        configured = run_git(target_root, "config", key, value)
        if configured.returncode != 0:
            raise AssertionError(configured.stderr)
    added_remote = run_git(target_root, "remote", "add", "origin", remote)
    if added_remote.returncode != 0:
        raise AssertionError(added_remote.stderr)
    for relative_name, content in files.items():
        target = target_root / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    staged = run_git(target_root, "add", "--all")
    if staged.returncode != 0:
        raise AssertionError(staged.stderr)
    committed = run_git(target_root, "commit", "-m", "test fixture")
    if committed.returncode != 0:
        raise AssertionError(committed.stderr)
    return target_root


def run_synchronizer(
    generated_root: Path,
    target_root: Path,
) -> subprocess.CompletedProcess[str]:
    if not SYNCHRONIZER_PATH.is_file():
        raise AssertionError("plugin distribution synchronizer module is required")
    return subprocess.run(
        (
            sys.executable,
            str(SYNCHRONIZER_PATH),
            "--generated-root",
            str(generated_root),
            "--target-root",
            str(target_root),
            "--expected-remote",
            EXPECTED_REMOTE,
        ),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def ownership_record(
    managed_files: list[str],
    *,
    version: str = VERSION,
    source_revision: str = SOURCE_REVISION,
) -> str:
    return (
        json.dumps(
            {
                "managed_files": sorted(managed_files),
                "schema_version": "1.0",
                "source_revision": source_revision,
                "version": version,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


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

    def test_generated_plugin_check_succeeds_outside_canonical_repository(self) -> None:
        """Generated Plugin 的檢查不得依賴 canonical repository 祖先目錄。"""
        builder = load_builder(self)
        tree = builder.build_distribution_tree(
            ROOT,
            version=VERSION,
            source_revision=SOURCE_REVISION,
        )

        with tempfile.TemporaryDirectory(prefix="workflow-skill-router-plugin-") as directory:
            output = Path(directory) / "plugin-repository"
            builder.write_distribution_tree(tree, output)
            npm = "npm.cmd" if os.name == "nt" else "npm"
            for command in ((npm, "ci"), (npm, "run", "check")):
                completed = subprocess.run(
                    command,
                    cwd=output,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    "Command failed: "
                    f"{' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
                )

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


class PluginDistributionSynchronizerTests(unittest.TestCase):
    def test_wrong_origin_fails_before_mutation_with_target_identity_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"README.md": "generated\n"},
            )
            target_root = create_target_repository(
                workspace,
                {"README.md": "existing\n"},
                remote="https://github.com/example/not-the-target.git",
            )

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(completed.stderr, r"(?i)target identity")
            self.assertEqual(
                (target_root / "README.md").read_text(encoding="utf-8"),
                "existing\n",
            )
            self.assertFalse(
                (target_root / ".workflow-skill-router-distribution.json").exists()
            )

    def test_dirty_target_checkout_fails_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"README.md": "generated\n"},
            )
            target_root = create_target_repository(
                workspace,
                {"README.md": "existing\n"},
            )
            dirty_file = target_root / "dirty.txt"
            dirty_file.write_text("do not touch\n", encoding="utf-8")

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(completed.stderr, r"(?i)(dirty|clean)")
            self.assertEqual(dirty_file.read_text(encoding="utf-8"), "do not touch\n")
            self.assertEqual(
                (target_root / "README.md").read_text(encoding="utf-8"),
                "existing\n",
            )
            self.assertFalse(
                (target_root / ".workflow-skill-router-distribution.json").exists()
            )

    def test_unmanaged_tracked_file_fails_closed_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"README.md": "generated\n"},
            )
            target_root = create_target_repository(
                workspace,
                {
                    "README.md": "existing\n",
                    "unexpected.txt": "preserve me\n",
                },
            )

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unmanaged tracked file", completed.stderr.lower())
            self.assertEqual(
                (target_root / "unexpected.txt").read_text(encoding="utf-8"),
                "preserve me\n",
            )
            self.assertEqual(
                (target_root / "README.md").read_text(encoding="utf-8"),
                "existing\n",
            )

    def test_later_tree_removes_only_prior_owned_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"keep.txt": "keep\n"},
                version="2.0.2",
                source_revision="b" * 40,
            )
            managed_files = ["keep.txt", "obsolete.txt", "release.json"]
            target_root = create_target_repository(
                workspace,
                {
                    ".workflow-skill-router-distribution.json": ownership_record(
                        managed_files
                    ),
                    "keep.txt": "keep\n",
                    "obsolete.txt": "remove me\n",
                    "release.json": ownership_record([]),
                },
            )

            completed = run_synchronizer(generated_root, target_root)

            self.assertEqual(
                completed.returncode,
                0,
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )
            self.assertFalse((target_root / "obsolete.txt").exists())
            record = json.loads(
                (
                    target_root / ".workflow-skill-router-distribution.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                record,
                {
                    "managed_files": ["keep.txt", "release.json"],
                    "schema_version": "1.0",
                    "source_revision": "b" * 40,
                    "version": "2.0.2",
                },
            )

    def test_prior_owned_symlink_or_junction_is_never_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"keep.txt": "keep\n"},
                version="2.0.2",
                source_revision="b" * 40,
            )
            managed_files = [
                "keep.txt",
                "link-target.txt",
                "obsolete-link.txt",
                "release.json",
            ]
            target_root = create_target_repository(
                workspace,
                {
                    ".workflow-skill-router-distribution.json": ownership_record(
                        managed_files
                    ),
                    "keep.txt": "keep\n",
                    "link-target.txt": "preserve target\n",
                    "release.json": ownership_record([]),
                },
            )
            configured = run_git(target_root, "config", "core.symlinks", "true")
            self.assertEqual(configured.returncode, 0, configured.stderr)
            link = target_root / "obsolete-link.txt"
            junction_target = workspace / "junction-target"
            used_junction = False
            try:
                link.symlink_to("link-target.txt")
            except OSError as error:
                if os.name != "nt":
                    self.fail(f"file symlink fixture failed: {error}")
                junction_target.mkdir()
                created = subprocess.run(
                    (
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        (
                            "New-Item -ItemType Junction "
                            f"-Path '{link}' "
                            f"-Target '{junction_target}' | Out-Null"
                        ),
                    ),
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(created.returncode, 0, created.stderr)
                used_junction = True
            if not used_junction:
                staged = run_git(target_root, "add", "obsolete-link.txt")
                self.assertEqual(staged.returncode, 0, staged.stderr)
                committed = run_git(target_root, "commit", "-m", "add managed symlink")
                self.assertEqual(committed.returncode, 0, committed.stderr)
            clean = run_git(target_root, "status", "--porcelain=v1")
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertEqual(clean.stdout, "")

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(completed.stderr, r"(?i)(symlink|junction|reparse)")
            self.assertTrue(link.exists())
            if used_junction:
                self.assertTrue(link.is_junction())
            else:
                self.assertTrue(link.is_symlink())
                self.assertEqual(os.readlink(link), "link-target.txt")

    def test_prior_ownership_cannot_claim_git_metadata_for_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {"keep.txt": "keep\n"},
                version="2.0.2",
                source_revision="b" * 40,
            )
            target_root = create_target_repository(
                workspace,
                {
                    ".workflow-skill-router-distribution.json": ownership_record(
                        [".git/config", "keep.txt", "release.json"]
                    ),
                    "keep.txt": "keep\n",
                    "release.json": ownership_record([]),
                },
            )
            git_config = target_root / ".git" / "config"
            original_config = git_config.read_bytes()

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(completed.stderr, r"(?i)(unsafe|reserved|git metadata)")
            self.assertTrue(git_config.is_file())
            self.assertEqual(git_config.read_bytes(), original_config)

    def test_ignored_untracked_ownership_record_cannot_authorize_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            generated_root = create_generated_root(
                workspace,
                {
                    ".gitignore": f"{OWNERSHIP_FILENAME}\n",
                    "keep.txt": "keep\n",
                },
                version="2.0.2",
                source_revision="b" * 40,
            )
            target_root = create_target_repository(
                workspace,
                {
                    ".gitignore": f"{OWNERSHIP_FILENAME}\n",
                    "keep.txt": "keep\n",
                    "release.json": ownership_record([]),
                    "unexpected.txt": "preserve me\n",
                },
            )
            forged_record = target_root / OWNERSHIP_FILENAME
            forged_record.write_text(
                ownership_record(
                    [".gitignore", "keep.txt", "release.json", "unexpected.txt"]
                ),
                encoding="utf-8",
            )
            clean = run_git(target_root, "status", "--porcelain=v1")
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertEqual(clean.stdout, "")

            completed = run_synchronizer(generated_root, target_root)

            self.assertNotEqual(completed.returncode, 0)
            self.assertRegex(completed.stderr, r"(?i)ownership record.*tracked")
            self.assertEqual(
                (target_root / "unexpected.txt").read_text(encoding="utf-8"),
                "preserve me\n",
            )


if __name__ == "__main__":
    unittest.main()
