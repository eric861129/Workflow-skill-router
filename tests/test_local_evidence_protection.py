from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages" / "router-core" / "src"
if str(CORE_SOURCE) not in os.sys.path:
    os.sys.path.insert(0, str(CORE_SOURCE))

from workflow_skill_router.evaluation.local_evidence import (
    EvidenceProtectionError,
    LocalEvidenceProtector,
)
import workflow_skill_router.evaluation.local_evidence as local_evidence


class LocalEvidenceProtectionTests(unittest.TestCase):
    def test_protects_directory_and_file_with_verified_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            restricted = Path(directory) / "restricted"
            restricted.mkdir()
            artifact = restricted / "raw-results.json"

            protector = LocalEvidenceProtector()
            protector.protect_directory(restricted)
            artifact.write_text('{"secret":"fixture"}', encoding="utf-8")
            protector.protect_file(artifact)

            self.assertTrue(protector.verify_directory(restricted))
            self.assertTrue(protector.verify_file(artifact))
            if os.name == "nt":
                for path in (restricted, artifact):
                    acl = self._windows_acl(path)
                    self.assertTrue(acl["protected"])
                    self.assertEqual(0, acl["inherited_rule_count"])
                    self.assertGreaterEqual(len(acl["identities"]), 1)
                    self.assertTrue(
                        set(acl["identities"]).issubset({acl["current_sid"], "S-1-5-18"})
                    )
            else:
                self.assertEqual(0o700, stat.S_IMODE(restricted.stat().st_mode))
                self.assertEqual(0o600, stat.S_IMODE(artifact.stat().st_mode))

    def test_unprotected_or_missing_path_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plain.json"
            path.write_text("{}", encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o644)
            protector = LocalEvidenceProtector()
            self.assertFalse(protector.verify_file(path))
            self.assertFalse(protector.verify_file(path.with_name("missing.json")))

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell environment contract")
    def test_powershell_receives_only_minimum_environment(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "{}", "")
        with patch.dict(
            os.environ,
            {"WORKFLOW_ROUTER_TEST_SECRET": "must-not-leak"},
        ), patch.object(local_evidence, "_RUN_PROCESS", return_value=completed) as run:
            LocalEvidenceProtector._run_powershell(
                "Write-Output '{}'",
                Path("C:/safe/evidence.json"),
                "file",
            )

        environment = run.call_args.kwargs["env"]
        self.assertNotIn("WORKFLOW_ROUTER_TEST_SECRET", environment)
        self.assertEqual(
            "C:/safe/evidence.json",
            Path(environment["WSR_EVIDENCE_PATH"]).as_posix(),
        )
        self.assertEqual("file", environment["WSR_EVIDENCE_KIND"])
        self.assertTrue(set(environment).issubset({
            "ComSpec", "LOCALAPPDATA", "PATH", "PATHEXT", "PSModulePath", "SystemRoot",
            "TEMP", "TMP", "USERPROFILE", "WINDIR", "WSR_EVIDENCE_KIND",
            "WSR_EVIDENCE_PATH",
        }))

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell error contract")
    def test_powershell_stderr_fails_closed_even_with_zero_exit_code(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "{}", "acl warning")
        with patch.object(local_evidence, "_RUN_PROCESS", return_value=completed):
            with self.assertRaisesRegex(
                EvidenceProtectionError,
                "windows_acl_command_rejected",
            ):
                LocalEvidenceProtector._run_powershell(
                    "Write-Output '{}'",
                    Path("C:/safe/evidence.json"),
                )

    def test_protector_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.mkdir()
            protector = LocalEvidenceProtector()
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaisesRegex(
                    EvidenceProtectionError,
                    "evidence_private_directory_symlink",
                ):
                    protector.protect_directory(target)
                self.assertFalse(protector.verify_directory(target))

    def test_windows_protector_rejects_junction_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.mkdir()
            protector = LocalEvidenceProtector(platform_name="nt")
            with (
                patch.object(Path, "is_symlink", return_value=False),
                patch.object(Path, "is_junction", return_value=True, create=True),
            ):
                with self.assertRaisesRegex(
                    EvidenceProtectionError,
                    "evidence_private_directory_symlink",
                ):
                    protector.protect_directory(target)
                self.assertFalse(protector.verify_directory(target))

    def test_windows_acl_invalid_json_shape_fails_closed(self) -> None:
        with patch.object(LocalEvidenceProtector, "_run_powershell", return_value="[]"):
            self.assertFalse(LocalEvidenceProtector._verify_windows_acl(Path("evidence")))

    @staticmethod
    def _windows_acl(path: Path) -> dict[str, object]:
        powershell = (
            Path(os.environ["SystemRoot"])
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        script = (
            "$acl=Get-Acl -LiteralPath $env:WSR_EVIDENCE_PATH;"
            "$rules=@($acl.Access);"
            "$ids=@($rules|ForEach-Object{"
            "try{$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value}"
            "catch{$_.IdentityReference.Value}}|Sort-Object -Unique);"
            "[pscustomobject]@{protected=$acl.AreAccessRulesProtected;"
            "inherited_rule_count=@($rules|Where-Object{$_.IsInherited}).Count;"
            "identities=$ids;current_sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value}"
            "|ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", "-"],
            input=script,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env={**os.environ, "WSR_EVIDENCE_PATH": str(path)},
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
