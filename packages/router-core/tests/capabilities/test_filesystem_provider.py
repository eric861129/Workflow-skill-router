from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.filesystem import (
    FilesystemMetadataProvider,
    InstallerContentClaim,
    InstallerManifestIndex,
)
from workflow_skill_router.capabilities.models import AuthState, Exposure
from workflow_skill_router.capabilities.providers import DiscoveryContext


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)
DIGEST = "sha256:" + "a" * 64


def write_skill(path: Path, body: str, metadata: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "name: demo\n"
        "description: first\n"
        f"{metadata}"
        "---\n"
        f"{body}\n",
        encoding="utf-8",
    )


class FilesystemProviderTests(unittest.TestCase):
    def provider(self, root: Path, index: InstallerManifestIndex | None = None):
        return FilesystemMetadataProvider((root,), installer_index=index, clock=lambda: NOW)

    def test_identity_is_source_qualified_and_body_is_excluded_from_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "demo" / "SKILL.md"
            write_skill(skill, "# instruction A")
            provider = self.provider(Path(directory))
            first = provider.discover(DiscoveryContext("runtime", "R0")).observations[0]
            write_skill(skill, "# instruction B")
            second = provider.discover(DiscoveryContext("runtime", "R0")).observations[0]
            self.assertEqual("skill:filesystem/demo", first.canonical_id)
            self.assertEqual(
                first.fields["capability_fingerprint"].value,
                second.fields["capability_fingerprint"].value,
            )

    def test_discovery_preserves_trusted_installer_digest_without_opening_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo" / "SKILL.md"
            write_skill(skill, "# secret instruction")
            claim = InstallerContentClaim(
                installer_identity="installer:test",
                manifest_digest="sha256:" + "b" * 64,
                content_digest=DIGEST,
            )
            index = InstallerManifestIndex({skill: claim})
            observation = self.provider(root, index).discover(
                DiscoveryContext("runtime", "R1")
            ).observations[0]
            self.assertEqual(DIGEST, observation.fields["installer_content_digest"].value)
            self.assertEqual(
                "trusted-installer-manifest",
                observation.fields["installer_content_digest"].reason_code,
            )

    def test_self_declared_content_digest_is_ignored_without_installer_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo" / "SKILL.md"
            write_skill(skill, "# instruction", f"installer_content_digest: {DIGEST}\n")
            provider = self.provider(root)
            observation = provider.discover(
                DiscoveryContext("runtime", "R1")
            ).observations[0]
            self.assertEqual("unknown", observation.fields["installer_content_digest"].value)
            self.assertEqual(Exposure.UNKNOWN, observation.fields["exposure"].value)
            self.assertEqual(AuthState.UNKNOWN, observation.fields["auth_state"].value)
            write_skill(
                skill,
                "# instruction",
                "installer_content_digest: sha256:" + "c" * 64 + "\n",
            )
            changed = provider.discover(DiscoveryContext("runtime", "R1")).observations[0]
            self.assertEqual("unknown", changed.fields["installer_content_digest"].value)
            self.assertNotEqual(
                observation.fields["capability_fingerprint"].value,
                changed.fields["capability_fingerprint"].value,
            )

    def test_invalid_skill_is_reported_as_degraded_without_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_bytes(b"---\nname: \xff\n---\nbody")
            result = self.provider(root).discover(DiscoveryContext("runtime", "R0"))
            self.assertEqual((), result.observations)
            self.assertTrue(result.degraded)
            self.assertTrue(any("frontmatter-invalid" in reason for reason in result.reasons))

    def test_symlinked_skill_outside_trusted_root_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            external = Path(outside) / "external"
            write_skill(external / "SKILL.md", "# outside")
            root.mkdir(exist_ok=True)
            link = root / "linked"
            try:
                link.symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"此環境無法建立 symlink: {error}")
            result = self.provider(root).discover(DiscoveryContext("runtime", "R0"))
            self.assertEqual((), result.observations)


if __name__ == "__main__":
    unittest.main()
