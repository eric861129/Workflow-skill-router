from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import stat

from workflow_skill_router.schemas.artifacts import canonical_json_bytes

from .frontmatter import FrontmatterError, parse_frontmatter, read_frontmatter_stream
from .models import (
    AuthState,
    CapabilityKind,
    Compatibility,
    Eligibility,
    Exposure,
    FieldObservation,
    Freshness,
    Presence,
    SideEffect,
    TrustLevel,
)
from .providers import CapabilityObservation, DiscoveryContext, ProviderResult


_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class InstallerContentClaim:
    installer_identity: str
    manifest_digest: str
    content_digest: str

    def __post_init__(self) -> None:
        if not self.installer_identity:
            raise ValueError("installer_identity 不可為空")
        for name, value in (
            ("manifest_digest", self.manifest_digest),
            ("content_digest", self.content_digest),
        ):
            if not _DIGEST_PATTERN.fullmatch(value):
                raise ValueError(f"{name} 必須是 lowercase sha256 digest")


class InstallerManifestIndex:
    """由受信 installer adapter 建立的不可變 content claim index。"""

    def __init__(self, claims: Mapping[Path, InstallerContentClaim] | None = None) -> None:
        normalized: dict[str, InstallerContentClaim] = {}
        for path, claim in (claims or {}).items():
            key = self._key(path)
            if key in normalized and normalized[key] != claim:
                raise ValueError(f"同一路徑存在互斥 installer claim: {path}")
            normalized[key] = claim
        self._claims = normalized

    @staticmethod
    def _key(path: Path) -> str:
        return os.path.normcase(str(path.resolve(strict=False)))

    def lookup(self, skill_path: Path) -> InstallerContentClaim | None:
        return self._claims.get(self._key(skill_path))


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(attributes & reparse)
    except OSError:
        return True


def _normalized_name(value: str) -> str:
    normalized = _NAME_PATTERN.sub("-", value.strip().lower()).strip("-")
    if not normalized:
        raise FrontmatterError("frontmatter name 無法形成 capability identity")
    return normalized


def _csv_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value.strip():
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


class FilesystemMetadataProvider:
    """只從受信根目錄讀取 SKILL frontmatter 的 metadata provider。"""

    provider_id = "filesystem"

    def __init__(
        self,
        roots: tuple[Path, ...],
        *,
        installer_index: InstallerManifestIndex | None = None,
        clock: Callable[[], datetime] | None = None,
        max_frontmatter_bytes: int = 65536,
        freshness_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not roots:
            raise ValueError("FilesystemMetadataProvider 至少需要一個 trusted root")
        if max_frontmatter_bytes <= 0:
            raise ValueError("max_frontmatter_bytes 必須大於 0")
        self._roots = tuple(path.resolve(strict=False) for path in roots)
        self._installer_index = installer_index or InstallerManifestIndex()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_frontmatter_bytes = max_frontmatter_bytes
        self._freshness_ttl = freshness_ttl

    def _iter_skill_paths(self, root: Path):
        if not root.is_dir() or _is_link_or_reparse(root):
            return
        for current, directories, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = sorted(
                name
                for name in directories
                if not _is_link_or_reparse(current_path / name)
            )
            if "SKILL.md" not in files:
                continue
            candidate = current_path / "SKILL.md"
            if _is_link_or_reparse(candidate):
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_relative_to(root):
                continue
            yield resolved

    def _observation(
        self,
        value: object,
        now: datetime,
        reason_code: str,
        trust_level: TrustLevel = TrustLevel.METADATA,
    ) -> FieldObservation[object]:
        return FieldObservation(value, self.provider_id, now, trust_level, reason_code)

    def _materialize(
        self,
        skill_path: Path,
        metadata: Mapping[str, object],
        now: datetime,
    ) -> CapabilityObservation:
        name = str(metadata["name"])
        canonical_id = f"skill:filesystem/{_normalized_name(name)}"
        nested = metadata.get("metadata")
        nested_metadata = nested if isinstance(nested, Mapping) else {}
        fingerprint_payload = {key: metadata[key] for key in sorted(metadata)}
        fingerprint = "sha256:" + hashlib.sha256(
            canonical_json_bytes(fingerprint_payload)
        ).hexdigest()

        claim = self._installer_index.lookup(skill_path)
        if claim is None:
            installer_digest = self._observation(
                "unknown",
                now,
                "installer-content-unverified",
            )
        else:
            installer_digest = self._observation(
                claim.content_digest,
                now,
                "trusted-installer-manifest",
                TrustLevel.HANDSHAKE,
            )

        side_effect_value = nested_metadata.get("side_effect", metadata.get("side_effect", "none"))
        try:
            side_effect = SideEffect(str(side_effect_value))
        except ValueError as error:
            raise FrontmatterError("metadata.side_effect 無效") from error
        context_cost_raw = nested_metadata.get("context_cost", metadata.get("context_cost", "1"))
        try:
            context_cost = int(str(context_cost_raw))
        except ValueError as error:
            raise FrontmatterError("metadata.context_cost 必須是整數") from error
        if context_cost < 0:
            raise FrontmatterError("metadata.context_cost 不可小於 0")

        description = metadata.get("description", "")
        if not isinstance(description, str):
            raise FrontmatterError("description 必須是字串")
        fields = {
            "display_name": self._observation(name, now, "frontmatter-name"),
            "description": self._observation(description, now, "frontmatter-description"),
            "presence": self._observation(Presence.PRESENT, now, "filesystem-present"),
            "exposure": self._observation(Exposure.UNKNOWN, now, "runtime-exposure-unverified"),
            "auth_state": self._observation(AuthState.UNKNOWN, now, "auth-state-unverified"),
            "eligibility": self._observation(Eligibility.UNKNOWN, now, "policy-unverified"),
            "compatibility": self._observation(
                Compatibility.UNKNOWN,
                now,
                "compatibility-unverified",
            ),
            "freshness": self._observation(
                Freshness(now, now + self._freshness_ttl, True),
                now,
                "filesystem-scan",
            ),
            "domains": self._observation(
                _csv_tuple(nested_metadata.get("domains", metadata.get("domains"))),
                now,
                "frontmatter-domains",
            ),
            "stages": self._observation(
                _csv_tuple(nested_metadata.get("stages", metadata.get("stages"))),
                now,
                "frontmatter-stages",
            ),
            "side_effect": self._observation(side_effect, now, "frontmatter-side-effect"),
            "requirements": self._observation((), now, "requirements-not-declared"),
            "aliases": self._observation(
                _csv_tuple(nested_metadata.get("aliases", metadata.get("aliases"))),
                now,
                "frontmatter-aliases",
            ),
            "conflicts": self._observation(
                _csv_tuple(nested_metadata.get("conflicts", metadata.get("conflicts"))),
                now,
                "frontmatter-conflicts",
            ),
            "context_cost": self._observation(context_cost, now, "frontmatter-context-cost"),
            "capability_fingerprint": self._observation(
                fingerprint,
                now,
                "frontmatter-fingerprint",
            ),
            "installer_content_digest": installer_digest,
        }
        return CapabilityObservation(
            canonical_id=canonical_id,
            kind=CapabilityKind.SKILL,
            source=self.provider_id,
            fields=fields,
        )

    def discover(self, context: DiscoveryContext) -> ProviderResult:
        del context  # Filesystem metadata 不得自行推論 runtime authority。
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock 必須回傳含 timezone 的 datetime")
        observations: list[CapabilityObservation] = []
        reasons: list[str] = []
        seen_paths: set[str] = set()
        for root in sorted(self._roots, key=lambda item: os.path.normcase(str(item))):
            if not root.is_dir() or _is_link_or_reparse(root):
                reasons.append("trusted-root-unavailable")
                continue
            for skill_path in self._iter_skill_paths(root):
                key = os.path.normcase(str(skill_path))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                try:
                    with skill_path.open("rb") as stream:
                        header = read_frontmatter_stream(
                            stream,
                            max_bytes=self._max_frontmatter_bytes,
                        )
                    metadata = parse_frontmatter(header)
                    observations.append(self._materialize(skill_path, metadata, now))
                except (OSError, FrontmatterError) as error:
                    reasons.append(f"frontmatter-invalid:{error.__class__.__name__}")

        observations.sort(key=lambda item: item.canonical_id)
        revision_payload = {
            "provider_id": self.provider_id,
            "observations": [
                {
                    "canonical_id": item.canonical_id,
                    "fingerprint": item.fields["capability_fingerprint"].value,
                    "installer_content_digest": item.fields["installer_content_digest"].value,
                }
                for item in observations
            ],
            "reasons": sorted(reasons),
        }
        revision = "sha256:" + hashlib.sha256(
            canonical_json_bytes(revision_payload)
        ).hexdigest()
        return ProviderResult(
            provider_id=self.provider_id,
            revision=revision,
            observed_at=now,
            observations=tuple(observations),
            degraded=bool(reasons),
            reasons=tuple(sorted(reasons)),
        )
