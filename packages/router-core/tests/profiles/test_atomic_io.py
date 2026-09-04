from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workflow_skill_router.profiles.atomic_io import (
    ProfileIOError,
    atomic_write_canonical_json,
    current_json_digest,
    secure_read_json,
)
from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.schemas.artifacts import canonical_json


def profile_document(*, primary: str = "skill:api-designer") -> dict[str, object]:
    return {
        "schema_id": "workflow-skill-router/routing-profile",
        "schema_version": "1.0.0",
        "artifact_kind": "routing-profile",
        "profile_id": "personal:adaptive-memory",
        "scope": "personal",
        "enabled": True,
        "rules": [
            {
                "rule_id": "api-delivery",
                "priority": 100,
                "match": {
                    "objective_keywords": ["student api"],
                    "domains": ["api"],
                    "tags": [],
                    "work_modes": ["single"],
                },
                "route": {
                    "work_mode": "single",
                    "skill_tree": [
                        {
                            "phase_id": "delivery",
                            "primary_skill_id": primary,
                            "support_skill_ids": [],
                            "exit_gate": "delivery-complete",
                        }
                    ],
                },
            }
        ],
    }


class AtomicProfileIoTests(unittest.TestCase):
    def test_atomic_write_creates_canonical_profile_and_returns_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "profiles/personal/adaptive-memory.json"
            document = profile_document()

            digest = atomic_write_canonical_json(
                target,
                root,
                document,
                expected_digest="missing",
            )

            decoded = secure_read_json(target, root)
            self.assertEqual(document, decoded)
            self.assertEqual(canonical_json(document) + "\n", target.read_text(encoding="utf-8"))
            self.assertEqual(decode_routing_profile(document).profile_digest, digest)
            self.assertEqual(digest, current_json_digest(target, root))
            self.assertEqual([], list(target.parent.glob(".*.tmp")))

    def test_compare_and_swap_rejects_drift_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "profile.json"
            first = profile_document(primary="skill:first")
            second = profile_document(primary="skill:second")
            first_digest = atomic_write_canonical_json(target, root, first, expected_digest="missing")
            target.write_text(canonical_json(second) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ProfileIOError, "profile-drift"):
                atomic_write_canonical_json(target, root, first, expected_digest=first_digest)

            self.assertEqual(second, secure_read_json(target, root))

    def test_missing_target_cannot_be_replaced_when_expected_digest_is_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "profile.json"

            with self.assertRaisesRegex(ProfileIOError, "profile-drift"):
                atomic_write_canonical_json(
                    target,
                    root,
                    profile_document(),
                    expected_digest="sha256:" + "a" * 64,
                )

            self.assertFalse(target.exists())

    def test_links_and_root_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "profile.json").write_text(
                canonical_json(profile_document()) + "\n",
                encoding="utf-8",
            )
            linked = root / "linked.json"
            try:
                linked.symlink_to(outside / "profile.json")
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable")

            with self.assertRaisesRegex(ProfileIOError, "profile-path-link-forbidden"):
                secure_read_json(linked, root)
            with self.assertRaisesRegex(ProfileIOError, "profile-path-escaped-root"):
                secure_read_json(outside / "profile.json", root)

    def test_failed_replace_cleans_same_directory_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "profiles/adaptive-memory.json"

            with patch.object(os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(ProfileIOError, "profile-atomic-write-failed"):
                    atomic_write_canonical_json(
                        target,
                        root,
                        profile_document(),
                        expected_digest="missing",
                    )

            self.assertFalse(target.exists())
            self.assertEqual([], list(target.parent.glob(".*.tmp")))


if __name__ == "__main__":
    unittest.main()
