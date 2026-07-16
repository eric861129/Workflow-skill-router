import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class ReleaseArtifactTests(unittest.TestCase):
    def test_generated_release_is_current_and_channels_do_not_promote_prerelease(self):
        result = subprocess.run([sys.executable, "scripts/build-release-artifacts.py", "--check"], cwd=ROOT,
                                text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        import json
        latest = json.loads((ROOT / "downloads/channels/latest.json").read_text("utf-8"))
        latest_v2 = json.loads((ROOT / "downloads/channels/latest-v2.json").read_text("utf-8"))
        self.assertEqual("1.3.1", latest["version"])
        self.assertEqual("2.0.0-alpha.1", latest_v2["version"])

    def test_archives_have_safe_sorted_paths_and_v2_skill_matches_source(self):
        archive_path = ROOT / "downloads/workflow-skill-router-skill-v2.0.0-alpha.1.zip"
        with ZipFile(archive_path) as archive:
            names = archive.namelist(); self.assertEqual(sorted(names), names)
            self.assertTrue(all(not name.startswith("/") and ".." not in Path(name).parts for name in names))
            self.assertEqual((ROOT / "starter/v2/workflow-skill-router/SKILL.md").read_bytes(),
                             archive.read("workflow-skill-router/SKILL.md"))


if __name__ == "__main__": unittest.main()
