import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-release-artifacts.py"
SPEC = importlib.util.spec_from_file_location("build_release_artifacts", BUILDER)
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class ReleaseOutputDirectoryTests(unittest.TestCase):
    def test_builder_loads_its_bound_helper_without_mutating_sys_path(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")

        self.assertIn("spec_from_file_location", source)
        self.assertIn("release_path_safety.py", source)
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("from release_path_safety import", source)

    def test_allowlist_rejects_windows_paths_that_can_escape_the_package_root(
        self,
    ) -> None:
        unsafe_paths = (
            r"..\escape.txt",
            r"C:\escape.txt",
            "C:/escape.txt",
            r"\\server\share\escape.txt",
            r"\rooted\escape.txt",
            "/rooted/escape.txt",
            "//server/share/escape.txt",
        )

        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary) / "package"
            source_root.mkdir()
            allowlist_path = Path(temporary) / "allowlist.json"

            for unsafe_path in unsafe_paths:
                with self.subTest(unsafe_path=unsafe_path):
                    allowlist_path.write_text(
                        json.dumps({"files": [unsafe_path]}) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )

                    with self.assertRaisesRegex(ValueError, "unsafe allowlist path"):
                        builder.safe_allowlist_entries(
                            source_root,
                            "workflow-skill-router",
                            allowlist_path,
                            require_all=True,
                        )

    def test_allowlist_rejects_win32_normalized_segments_before_file_access(
        self,
    ) -> None:
        unsafe_paths = (
            "nested/.. /.. /escape.txt",
            "nested/... /... /... ",
            ". /escape.txt",
            "nested/.. ./escape.txt",
            "nested/..../escape.txt",
            "nested./escape.txt",
            "nested /escape.txt",
            "nested/CON.txt",
            "nested/name?.txt",
            "nested/AUX.txt",
            "nested/NUL.tar.gz",
            "nested/PRN.json",
            "nested/CONIN$.txt",
            "nested/CONOUT$.json",
            "nested/COM0.txt",
            "nested/com9.tar.gz",
            "nested/LPT0.txt",
            "nested/lpt9.json",
            "nested/COM\u00b9.txt",
            "nested/com\u00b2.tar.gz",
            "nested/LPT\u00b2.txt",
            "nested/LPT\u00b3.json",
        )

        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary) / "package"
            source_root.mkdir()
            allowlist_path = Path(temporary) / "allowlist.json"

            for unsafe_path in unsafe_paths:
                with self.subTest(unsafe_path=unsafe_path):
                    allowlist_path.write_text(
                        json.dumps({"files": [unsafe_path]}) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )

                    with patch.object(
                        Path,
                        "is_file",
                        side_effect=AssertionError("unsafe path was accessed"),
                    ), self.assertRaisesRegex(ValueError, "unsafe allowlist path"):
                        builder.safe_allowlist_entries(
                            source_root,
                            "workflow-skill-router",
                            allowlist_path,
                            require_all=True,
                        )

    def test_allowlist_accepts_non_reserved_device_like_components(self) -> None:
        safe_paths = (
            "nested/COM10.txt",
            "nested/LPT10.txt",
            "nested/COM\u2074.txt",
            "nested/CONTEXT.txt",
            "nested/CONIN.txt",
            "nested/CONOUT.txt",
            "nested/COM1PORT.txt",
        )

        for safe_path in safe_paths:
            with self.subTest(safe_path=safe_path):
                self.assertEqual(
                    safe_path,
                    builder.parse_safe_relative_posix_path(safe_path).as_posix(),
                )

    def test_cli_rejects_win32_normalized_allowlist_before_writing_output(
        self,
    ) -> None:
        unsafe_paths = (
            "nested/.. /.. /escape.txt",
            "nested/... /... /... ",
            ". /escape.txt",
            "nested/.. ./escape.txt",
            "nested/..../escape.txt",
            "nested./escape.txt",
            "nested/AUX.txt",
            "nested/NUL.tar.gz",
            "nested/PRN.json",
            "nested/CONIN$.txt",
            "nested/CONOUT$.json",
            "nested/COM0.txt",
            "nested/com9.tar.gz",
            "nested/LPT0.txt",
            "nested/lpt9.json",
            "nested/COM\u00b9.txt",
            "nested/com\u00b2.tar.gz",
            "nested/LPT\u00b2.txt",
            "nested/LPT\u00b3.json",
        )

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "release-fixture"
            scripts = repository / "scripts"
            allowlists = repository / "release" / "allowlists"
            scripts.mkdir(parents=True)
            allowlists.mkdir(parents=True)
            shutil.copy2(BUILDER, scripts / BUILDER.name)
            shutil.copy2(
                ROOT / "scripts" / "release_path_safety.py",
                scripts / "release_path_safety.py",
            )
            (repository / "release" / "version.json").write_text(
                '{"v2_version":"2.0.0-beta.4"}\n',
                encoding="utf-8",
                newline="\n",
            )

            for unsafe_path in unsafe_paths:
                with self.subTest(unsafe_path=unsafe_path):
                    (allowlists / "plugin-runtime-files.json").write_text(
                        json.dumps({"files": [unsafe_path]}) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    output = repository / "output"
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-S",
                            "-B",
                            str(scripts / BUILDER.name),
                            "--output-dir",
                            str(output),
                            "--provenance-mode",
                            "test",
                        ],
                        cwd=repository,
                        text=True,
                        capture_output=True,
                    )

                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("unsafe allowlist path", result.stderr)
                    self.assertFalse(output.exists())

    def test_cli_rejects_missing_required_plugin_runtime_file_before_writing_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "release-fixture"
            scripts = repository / "scripts"
            allowlists = repository / "release" / "allowlists"
            scripts.mkdir(parents=True)
            allowlists.mkdir(parents=True)
            (repository / "plugins" / "workflow-skill-router" / "mcp").mkdir(
                parents=True
            )
            shutil.copy2(BUILDER, scripts / BUILDER.name)
            shutil.copy2(
                ROOT / "scripts" / "release_path_safety.py",
                scripts / "release_path_safety.py",
            )
            (repository / "release" / "version.json").write_text(
                '{"v1_pinned_version":"1.3.1","v2_version":"2.0.0-beta.4"}\n',
                encoding="utf-8",
                newline="\n",
            )
            (allowlists / "plugin-runtime-files.json").write_text(
                '{"files":["mcp/server.bundle.mjs"]}\n',
                encoding="utf-8",
                newline="\n",
            )
            (allowlists / "skill-package.json").write_text(
                '{"files":[]}\n', encoding="utf-8", newline="\n"
            )
            output = repository / "output"

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    str(scripts / BUILDER.name),
                    "--output-dir",
                    str(output),
                    "--provenance-mode",
                    "test",
                ],
                cwd=repository,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn(
                "required allowlist file is missing or not a regular file: "
                "mcp/server.bundle.mjs",
                result.stderr,
            )
            self.assertFalse(output.exists())

    def test_isolated_builder_help_cannot_import_a_scripts_zipfile_shadow(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "release-fixture"
            scripts = repository / "scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(BUILDER, scripts / BUILDER.name)
            shutil.copy2(
                ROOT / "scripts" / "release_path_safety.py",
                scripts / "release_path_safety.py",
            )
            sentinel = repository / "zipfile-shadow-executed.txt"
            (scripts / "zipfile.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n"
                "raise RuntimeError('unbound zipfile shadow executed')\n",
                encoding="utf-8",
                newline="\n",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    str(scripts / BUILDER.name),
                    "--help",
                ],
                cwd=repository,
                text=True,
                capture_output=True,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("usage:", result.stdout)
            self.assertFalse(sentinel.exists())

    def test_cli_writes_deterministic_v2_release_tree_to_explicit_output(self) -> None:
        downloads_before = snapshot(ROOT / "downloads")
        version = json.loads(
            (ROOT / "release" / "version.json").read_text(encoding="utf-8")
        )["v2_version"]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            for output in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-B",
                        str(BUILDER),
                        "--output-dir",
                        str(output),
                        "--provenance-mode",
                        "test",
                        "--check-determinism",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

            self.assertTrue(
                (first / f"workflow-skill-router-plugin-v{version}.zip").is_file()
            )
            self.assertTrue(
                (
                    first
                    / "sbom"
                    / f"workflow-skill-router-v{version}.spdx.json"
                ).is_file()
            )
            self.assertTrue(
                (
                    first
                    / "provenance"
                    / f"workflow-skill-router-v{version}.json"
                ).is_file()
            )
            self.assertEqual(snapshot(first), snapshot(second))

        self.assertEqual(downloads_before, snapshot(ROOT / "downloads"))

    def test_cli_rejects_the_tracked_downloads_directory(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(BUILDER),
                "--output-dir",
                str(ROOT / "downloads"),
                "--provenance-mode",
                "test",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("tracked downloads", result.stderr)

    def test_cli_rejects_unexpected_stale_files_in_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "release"
            output.mkdir()
            stale = output / "workflow-skill-router-plugin-v2.0.0-alpha.1.zip"
            stale.write_bytes(b"stale-release-asset")

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    str(BUILDER),
                    "--output-dir",
                    str(output),
                    "--provenance-mode",
                    "test",
                    "--check-determinism",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("unexpected existing release output", result.stderr)
            self.assertEqual(b"stale-release-asset", stale.read_bytes())

    def test_release_provenance_binds_clean_head_and_tree(self) -> None:
        head = "a" * 40
        tree = "b" * 40
        with patch.object(builder, "git", side_effect=[head, "", tree]):
            provenance = builder.resolve_provenance("release", head, True)
        self.assertTrue(provenance.publishable)
        self.assertEqual(head, provenance.source_revision)
        self.assertEqual(tree, provenance.source_tree)

        with self.assertRaisesRegex(ValueError, "requires --require-clean"):
            builder.resolve_provenance("release", head, False)
        with patch.object(builder, "git", return_value="c" * 40):
            with self.assertRaisesRegex(ValueError, "does not match HEAD"):
                builder.resolve_provenance("release", head, True)
        with patch.object(builder, "git", side_effect=[head, " M README.md"]):
            with self.assertRaisesRegex(ValueError, "clean tracked worktree"):
                builder.resolve_provenance("release", head, True)


if __name__ == "__main__":
    unittest.main()
