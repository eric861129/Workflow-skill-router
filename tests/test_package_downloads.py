import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_downloads", ROOT / "scripts/package-downloads.py")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class PackageDownloadsTests(unittest.TestCase):
    def test_blank_archive_matches_starter_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "blank.zip"
            source = ROOT / "starter" / "workflow-skill-router"
            module.build_blank_archive(source, output)
            with ZipFile(output) as archive:
                for path in module.iter_files(source):
                    self.assertEqual(path.read_bytes(), archive.read("workflow-skill-router/" + path.relative_to(source).as_posix()))

    def test_manifest_uses_public_contract_labels(self):
        report = module.PackageReport(["workflow-skill-router"], 0, [], Path("skills"))
        text = module.manifest_text(report)
        for label in ("Blank Router", "Clean Template", "Full Template"):
            self.assertIn(label, text)


if __name__ == "__main__": unittest.main()
