import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "release" / "v2-open-source-reset-baseline.json"
CLOSURE_PATH = ROOT / "release" / "v2-inherited-change-closure.json"
ALLOWED_REMOVAL_MANIFESTS = {
    "release/legacy-v1-removal-manifest.json",
    "release/v2-residual-removal-manifest.json",
}
CANONICAL_TEXT_SUFFIXES = {
    ".css", ".json", ".jsonl", ".md", ".mjs", ".py", ".sql", ".ts", ".yaml", ".yml",
}


def sha256(path: Path) -> str:
    content = path.read_bytes()
    if path.suffix.casefold() in CANONICAL_TEXT_SUFFIXES:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


class InheritedChangeClosureTests(unittest.TestCase):
    def load_closure(self) -> dict[str, object]:
        self.assertTrue(CLOSURE_PATH.is_file(), "inherited-change closure is missing")
        return json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))

    def test_closure_matches_every_baseline_path_exactly_once(self) -> None:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        closure = self.load_closure()
        baseline_by_path = {
            item["path"]: item for item in baseline["inherited_changes"]
        }
        entries = closure["entries"]
        closure_paths = [item["path"] for item in entries]

        self.assertEqual("1.0", closure["schema_version"])
        self.assertEqual(baseline["starting_head"], closure["starting_head"])
        self.assertEqual(len(baseline_by_path), closure["entry_count"])
        self.assertEqual(len(closure_paths), len(set(closure_paths)))
        self.assertEqual(set(baseline_by_path), set(closure_paths))

        for entry in entries:
            with self.subTest(path=entry["path"]):
                self.assertEqual(
                    baseline_by_path[entry["path"]]["owner_task"],
                    entry["owner_task"],
                )
                self.assertIn(
                    entry["disposition"], {"incorporated", "superseded", "removed"}
                )

    def test_every_closure_evidence_is_non_circular_and_verifiable(self) -> None:
        closure = self.load_closure()
        removal_documents = {
            relative: json.loads((ROOT / relative).read_text(encoding="utf-8"))
            for relative in ALLOWED_REMOVAL_MANIFESTS
        }

        for entry in closure["entries"]:
            path = ROOT / entry["path"]
            evidence = entry["evidence"]
            kind = evidence["kind"]
            with self.subTest(path=entry["path"], kind=kind):
                self.assertIn(
                    kind, {"current-content-digest", "removal-manifest", "commit"}
                )
                if kind == "current-content-digest":
                    self.assertTrue(path.is_file())
                    self.assertEqual(sha256(path), evidence["sha256"])
                    self.assertNotEqual(CLOSURE_PATH.resolve(), path.resolve())
                elif kind == "removal-manifest":
                    manifest = evidence["manifest"]
                    self.assertIn(manifest, ALLOWED_REMOVAL_MANIFESTS)
                    self.assertIn(entry["path"], removal_documents[manifest]["files"])
                    self.assertFalse(path.exists())
                    self.assertEqual("removed", entry["disposition"])
                else:
                    revision = evidence["revision"]
                    self.assertRegex(revision, r"^[0-9a-f]{40}$")
                    result = subprocess.run(
                        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                        cwd=ROOT,
                        capture_output=True,
                    )
                    self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
