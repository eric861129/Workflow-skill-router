import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/workflow-skill-router/scripts/build-runtime.py"
SPEC = importlib.util.spec_from_file_location("build_runtime", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class RuntimeBuilderTests(unittest.TestCase):
    def test_runtime_includes_new_untracked_core_sources(self) -> None:
        members = {
            path.relative_to(module.SOURCE).as_posix()
            for path in module.eligible_files()
        }

        self.assertIn("workflow_skill_router/local_control.py", members)
        self.assertIn(
            "workflow_skill_router/persistence/migrations/0003_local_control_plane.sql",
            members,
        )

    def test_rebuilt_runtime_launches_doctor_and_jsonl_server(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "workflow_skill_router.pyz"
            build = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(runtime)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)

            doctor = subprocess.run(
                [sys.executable, str(runtime), "doctor"],
                cwd=root,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, doctor.returncode, doctor.stdout + doctor.stderr)
            self.assertIn('"runtime_status": "core-ready"', doctor.stdout)

            serve = subprocess.run(
                [
                    sys.executable,
                    str(runtime),
                    "serve-jsonl",
                    "--database",
                    str(root / "router.db"),
                ],
                cwd=root,
                input="",
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(0, serve.returncode, serve.stdout + serve.stderr)


if __name__ == "__main__":
    unittest.main()
