from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess


_RUN_PROCESS = subprocess.run
_POWERSHELL_ENV_ALLOWLIST = (
    "ComSpec",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PSModulePath",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
)


class EvidenceProtectionError(RuntimeError):
    """表示本機評測證據無法建立或驗證為私有。"""


class LocalEvidenceProtector:
    """以可驗證的主機權限保護本機 raw evaluation evidence。"""

    def __init__(self, *, platform_name: str | None = None) -> None:
        self._platform_name = platform_name or os.name

    def protect_directory(self, path: Path) -> None:
        if self._is_path_alias(path):
            raise EvidenceProtectionError("evidence_private_directory_symlink")
        if not path.is_dir():
            raise EvidenceProtectionError("evidence_private_directory_missing")
        if self._platform_name == "nt":
            self._apply_windows_acl(path, directory=True)
        else:
            path.chmod(0o700)
        if not self.verify_directory(path):
            raise EvidenceProtectionError("evidence_private_directory_unverified")

    def protect_file(self, path: Path) -> None:
        if self._is_path_alias(path):
            raise EvidenceProtectionError("evidence_private_file_symlink")
        if not path.is_file():
            raise EvidenceProtectionError("evidence_private_file_missing")
        if self._platform_name == "nt":
            self._apply_windows_acl(path, directory=False)
        else:
            path.chmod(0o600)
        if not self.verify_file(path):
            raise EvidenceProtectionError("evidence_private_file_unverified")

    def verify_directory(self, path: Path) -> bool:
        if self._is_path_alias(path) or not path.is_dir():
            return False
        if self._platform_name == "nt":
            return self._verify_windows_acl(path)
        return stat.S_IMODE(path.stat().st_mode) == 0o700

    def verify_file(self, path: Path) -> bool:
        if self._is_path_alias(path) or not path.is_file():
            return False
        if self._platform_name == "nt":
            return self._verify_windows_acl(path)
        return stat.S_IMODE(path.stat().st_mode) == 0o600

    def _is_path_alias(self, path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return (
            self._platform_name == "nt"
            and callable(is_junction)
            and is_junction()
        )

    @staticmethod
    def _powershell_executable() -> Path:
        system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if not system_root:
            raise EvidenceProtectionError("windows_system_root_missing")
        executable = (
            Path(system_root)
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        if not executable.is_file():
            raise EvidenceProtectionError("windows_powershell_missing")
        return executable

    @classmethod
    def _run_powershell(cls, script: str, path: Path, kind: str | None = None) -> str:
        environment = {
            name: os.environ[name]
            for name in _POWERSHELL_ENV_ALLOWLIST
            if name in os.environ
        }
        environment["WSR_EVIDENCE_PATH"] = str(path)
        environment["WSR_EVIDENCE_KIND"] = kind or ""
        command = [
            str(cls._powershell_executable()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "-",
        ]
        try:
            completed = _RUN_PROCESS(
                command,
                shell=False,
                input=script,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=15,
                check=False,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise EvidenceProtectionError("windows_acl_command_failed") from error
        if completed.returncode != 0 or completed.stderr.strip():
            raise EvidenceProtectionError("windows_acl_command_rejected")
        return completed.stdout.strip()

    @classmethod
    def _apply_windows_acl(cls, path: Path, *, directory: bool) -> None:
        script = (
            "$ErrorActionPreference='Stop';"
            "$path=$env:WSR_EVIDENCE_PATH;$kind=$env:WSR_EVIDENCE_KIND;"
            "$current=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
            "$rights=if($kind -eq 'directory'){'(OI)(CI)F'}else{'F'};"
            "$icacls=Join-Path $env:SystemRoot 'System32\\icacls.exe';"
            "& $icacls $path '/inheritance:r' '/grant:r' "
            "\"*$($current):$rights\" \"*S-1-5-18:$rights\"|Out-Null;"
            "if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}"
        )
        cls._run_powershell(script, path, "directory" if directory else "file")

    @classmethod
    def _verify_windows_acl(cls, path: Path) -> bool:
        script = (
            "$ErrorActionPreference='Stop';"
            "$acl=Get-Acl -LiteralPath $env:WSR_EVIDENCE_PATH;$rules=@($acl.Access);"
            "$current=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
            "$allowed=@($current,'S-1-5-18');$ids=@();$valid=$true;"
            "foreach($rule in $rules){"
            "try{$sid=$rule.IdentityReference.Translate("
            "[System.Security.Principal.SecurityIdentifier]).Value}catch{$valid=$false;continue};"
            "$ids+=$sid;"
            "if($rule.IsInherited -or $rule.AccessControlType -ne "
            "[System.Security.AccessControl.AccessControlType]::Allow){$valid=$false};"
            "if($allowed -notcontains $sid){$valid=$false};"
            "if(($rule.FileSystemRights -band "
            "[System.Security.AccessControl.FileSystemRights]::FullControl) -ne "
            "[System.Security.AccessControl.FileSystemRights]::FullControl){$valid=$false}};"
            "$unique=@($ids|Sort-Object -Unique);"
            "$private=$acl.AreAccessRulesProtected -and $valid -and "
            "($unique -contains $current) -and ($unique -contains 'S-1-5-18') -and "
            "($unique.Count -eq 2);"
            "[pscustomobject]@{private=$private}|ConvertTo-Json -Compress"
        )
        try:
            output = cls._run_powershell(script, path)
            parsed = json.loads(output)
        except (EvidenceProtectionError, json.JSONDecodeError):
            return False
        return isinstance(parsed, dict) and parsed.get("private") is True
