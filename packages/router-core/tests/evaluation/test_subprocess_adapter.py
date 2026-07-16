from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from workflow_skill_router.evaluation.contracts import (
    EvaluationIntegrityError,
    EvaluationProfile,
    ModelExecutionPayload,
    ModelTurnRequest,
)
from workflow_skill_router.evaluation.subprocess_adapter import SubprocessExecutionAdapter


DRIVER = r"""
import json
from pathlib import Path
import sys
import time

mode = sys.argv[1]
request = json.load(sys.stdin)
if mode == "timeout":
    time.sleep(2)
if mode == "non-json":
    print("not-json")
    raise SystemExit(0)
if mode == "stderr-only":
    print("driver failed", file=sys.stderr)
    raise SystemExit(7)
if mode == "oversized":
    print(json.dumps({"attempt_nonce": request["attempt_nonce"], "text": "x" * 4096}))
    raise SystemExit(0)
if mode == "record-argv":
    Path(sys.argv[2]).write_text(json.dumps(sys.argv[3:]), encoding="utf-8")
if request["type"] == "start_attempt":
    context_id = "fixed-context" if mode == "duplicate" else "ctx:" + request["attempt_nonce"]
    response = {"attempt_nonce": request["attempt_nonce"], "context_id": context_id}
else:
    response = {
        "attempt_nonce": "wrong" if mode == "wrong-nonce" else request["attempt_nonce"],
        "context_id": request["context_id"],
        "text": request["prompt"],
    }
print(json.dumps(response))
"""


class SubprocessAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.driver = self.root / "fake_driver.py"
        self.driver.write_text(DRIVER, encoding="utf-8")
        self.payload = ModelExecutionPayload(
            "opaque-case-1",
            "Route this task",
            EvaluationProfile.BEHAVIOR,
            ("read", "write"),
        )

    def adapter(self, mode: str = "ok", *arguments: str, **options) -> SubprocessExecutionAdapter:
        return SubprocessExecutionAdapter(
            (sys.executable, str(self.driver), mode, *arguments),
            **options,
        )

    def test_starts_attempt_and_preserves_nonce_across_turns(self):
        adapter = self.adapter()
        context_id = adapter.start_attempt(self.payload, "attempt-001")
        result = adapter.execute_turn(
            ModelTurnRequest("attempt-001", 0, "continue", ("read",)),
        )

        self.assertEqual("ctx:attempt-001", context_id)
        self.assertEqual("attempt-001", result["attempt_nonce"])
        self.assertEqual(context_id, result["context_id"])

    def test_requires_a_tuple_with_an_absolute_executable(self):
        for command in ("python driver.py", (), ("",), ("python", "driver.py")):
            with self.subTest(command=command), self.assertRaises(ValueError):
                SubprocessExecutionAdapter(command)  # type: ignore[arg-type]

    def test_shell_metacharacters_are_passed_as_literal_argv_data(self):
        record = self.root / "argv.json"
        marker = "literal;&|$()`whoami`"
        adapter = self.adapter("record-argv", str(record), marker)

        adapter.start_attempt(self.payload, "attempt-001")

        self.assertEqual([marker], json.loads(record.read_text(encoding="utf-8")))

    def test_rejects_nonce_mismatch(self):
        adapter = self.adapter("wrong-nonce")
        adapter.start_attempt(self.payload, "attempt-001")
        with self.assertRaisesRegex(EvaluationIntegrityError, "attempt_context_mismatch"):
            adapter.execute_turn(ModelTurnRequest("attempt-001", 0, "continue", ()))

    def test_rejects_duplicate_context_ids(self):
        adapter = self.adapter("duplicate")
        adapter.start_attempt(self.payload, "attempt-001")
        with self.assertRaisesRegex(EvaluationIntegrityError, "subprocess_context_not_fresh"):
            adapter.start_attempt(self.payload, "attempt-002")

    def test_rejects_non_json_output(self):
        with self.assertRaisesRegex(EvaluationIntegrityError, "subprocess_response_not_json"):
            self.adapter("non-json").start_attempt(self.payload, "attempt-001")

    def test_rejects_timeout(self):
        with self.assertRaisesRegex(EvaluationIntegrityError, "subprocess_timeout"):
            self.adapter("timeout", timeout_seconds=1).start_attempt(self.payload, "attempt-001")

    def test_rejects_stderr_only_failure(self):
        with self.assertRaisesRegex(EvaluationIntegrityError, "subprocess_failed"):
            self.adapter("stderr-only").start_attempt(self.payload, "attempt-001")

    def test_rejects_output_above_configured_limit(self):
        with self.assertRaisesRegex(EvaluationIntegrityError, "subprocess_output_too_large"):
            self.adapter("oversized", maximum_output_bytes=128).start_attempt(
                self.payload,
                "attempt-001",
            )


if __name__ == "__main__":
    unittest.main()
