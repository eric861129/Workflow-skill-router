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
    def test_locked_image_pipeline_includes_reviewed_security_fixes(self) -> None:
        lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        for name, minimum in (("astro", (7, 2, 8)), ("sharp", (0, 35, 5))):
            with self.subTest(package=name):
                self.assertGreaterEqual(
                    version_tuple(lock["packages"][f"node_modules/{name}"]["version"]),
                    minimum,
                )

    def test_site_declares_astro_security_floor(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))

        self.assertGreaterEqual(
            version_tuple(package["dependencies"]["astro"].lstrip("^~")),
            (7, 2, 8),
        )

    def test_site_declares_starlight_version_compatible_with_astro_7(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))

        self.assertGreaterEqual(
            version_tuple(package["dependencies"]["@astrojs/starlight"].lstrip("^~")),
            (0, 41, 4),
        )

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
