import importlib.util
import json
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
