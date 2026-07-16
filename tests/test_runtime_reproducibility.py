import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "workflow-skill-router"


class RuntimeReproducibilityTests(unittest.TestCase):
    def test_python_and_mcp_runtime_builds_are_reproducible_and_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            python_outputs = [temporary_root / f"runtime-{index}.pyz" for index in (1, 2)]
            mcp_outputs = [temporary_root / f"server-{index}.bundle.mjs" for index in (1, 2)]

            for output in python_outputs:
                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/build-runtime.py",
                        "--output",
                        str(output),
                    ],
                    cwd=PLUGIN,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

            for output in mcp_outputs:
                result = subprocess.run(
                    [
                        "node",
                        "scripts/build-mcp.mjs",
                        "--output",
                        str(output),
                    ],
                    cwd=PLUGIN,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

            self.assertEqual(python_outputs[0].read_bytes(), python_outputs[1].read_bytes())
            self.assertEqual(mcp_outputs[0].read_bytes(), mcp_outputs[1].read_bytes())
            self.assertEqual(
                (PLUGIN / "runtime/workflow_skill_router.pyz").read_bytes(),
                python_outputs[0].read_bytes(),
            )
            self.assertEqual(
                (PLUGIN / "mcp/server.bundle.mjs").read_bytes(),
                mcp_outputs[0].read_bytes(),
            )

            root_bytes = str(ROOT).encode("utf-8")
            self.assertNotIn(root_bytes, python_outputs[0].read_bytes())
            self.assertNotIn(root_bytes, mcp_outputs[0].read_bytes())
            self.assertNotIn(b"sourceMappingURL", mcp_outputs[0].read_bytes())

            with ZipFile(python_outputs[0]) as archive:
                names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertTrue(all("__pycache__" not in Path(name).parts for name in names))
            self.assertTrue(
                all(
                    name == "__main__.py"
                    or Path(name).suffix in {".py", ".json", ".sql"}
                    for name in names
                )
            )


if __name__ == "__main__":
    unittest.main()
