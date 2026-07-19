import contextlib
import io
import unittest

from workflow_skill_router.cli import main


class ConsoleTests(unittest.TestCase):
    def test_help_contains_same_public_command_tree(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(0, raised.exception.code)
        for command in ("serve-jsonl", "doctor", "status", "plan", "validate-route", "evaluation"):
            self.assertIn(command, output.getvalue())


if __name__ == "__main__": unittest.main()
