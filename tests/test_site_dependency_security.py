import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "site" / "package.json"
LOCKFILE = ROOT / "site" / "package-lock.json"
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.match(value)
    if not match:
        raise ValueError(f"Unsupported semantic version: {value}")
    return tuple(int(part) for part in match.groups())


class SiteDependencySecurityTests(unittest.TestCase):
    def test_locked_opentelemetry_core_versions_include_baggage_limit_fix(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        locked_versions = [
            package["version"]
            for path, package in lock["packages"].items()
            if path.endswith("node_modules/@opentelemetry/core")
        ]

        if "lighthouse" in package.get("overrides", {}):
            self.assertGreater(len(locked_versions), 0)

        for version in locked_versions:
            with self.subTest(version=version):
                self.assertGreaterEqual(version_tuple(version), (2, 8, 0))


if __name__ == "__main__":
    unittest.main()
