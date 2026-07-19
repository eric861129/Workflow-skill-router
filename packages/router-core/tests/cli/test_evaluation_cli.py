from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

from workflow_skill_router.cli import build_parser, main


class EvaluationCliTests(unittest.TestCase):
    def test_parser_preserves_adapter_arguments_as_separate_items(self):
        marker = "literal;&|$()"
        args = build_parser().parse_args([
            "evaluation", "run", "--profile", "behavior",
            "--evidence-class", "reference-driver", "--adapter", "subprocess",
            "--adapter-executable", sys.executable, "--adapter-arg", "driver.py",
            "--adapter-arg", marker, "--repeats", "3",
        ])

        self.assertEqual(["driver.py", marker], args.adapter_arg)
        self.assertFalse(hasattr(args, "adapter_command"))

    def test_reference_driver_prints_locked_dry_run_manifest_without_live_confirmation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main([
                "evaluation", "run", "--profile", "behavior",
                "--evidence-class", "reference-driver", "--adapter", "subprocess",
                "--adapter-executable", sys.executable, "--adapter-arg", "driver.py",
                "--repeats", "3",
            ])

        self.assertEqual(0, status)
        manifest = json.loads(output.getvalue())
        self.assertEqual("reference-driver", manifest["evidence_class"])
        self.assertTrue(manifest["evidence_class_locked"])
        self.assertFalse(manifest["live_run"])
        self.assertEqual([sys.executable, "driver.py"], manifest["adapter_command"])

    def test_behavior_live_run_requires_explicit_confirmation(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            status = main([
                "evaluation", "run", "--profile", "behavior",
                "--evidence-class", "fresh-model-execution", "--adapter", "subprocess",
                "--adapter-executable", sys.executable, "--adapter-arg", "driver.py",
                "--repeats", "3",
            ])

        self.assertEqual(2, status)
        self.assertIn("--confirm-live-run", error.getvalue())

    def test_executable_must_be_absolute(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            status = main([
                "evaluation", "run", "--profile", "contract",
                "--evidence-class", "reference-driver", "--adapter", "subprocess",
                "--adapter-executable", "python", "--adapter-arg", "driver.py",
            ])
        self.assertEqual(2, status)
        self.assertIn("absolute", error.getvalue())


if __name__ == "__main__":
    unittest.main()
