from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.managed_profiles import (
    ManagedProfilePathError,
    managed_personal_profile_path,
    managed_workspace_profile_path,
    verify_workspace_root,
)
from workflow_skill_router.profiles.layers import ProfileSourceClass
from workflow_skill_router.profiles.storage import (
    RoutingProfileRepository,
    RoutingProfileContractError,
)

from profiles.test_contract import profile_document


def write_profile(path: Path, *, scope: str, profile_id: str, primary: str) -> None:
    document = profile_document(scope=scope)
    document["profile_id"] = profile_id
    document["rules"][0]["route"]["skill_tree"][0]["primary_skill_id"] = primary
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


class ManagedProfileTests(unittest.TestCase):
    def test_fixed_paths_use_only_the_verified_workspace_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            identity = verify_workspace_root(workspace)

            self.assertRegex(identity.digest, r"^sha256:[0-9a-f]{64}$")
            self.assertNotIn(str(workspace), identity.digest)
            self.assertEqual(
                root / "state/profiles/managed/personal/adaptive-memory.json",
                managed_personal_profile_path(root / "state"),
            )
            self.assertEqual(
                root
                / "state/profiles/managed/workspace"
                / identity.digest.removeprefix("sha256:")
                / "adaptive-memory.json",
                managed_workspace_profile_path(root / "state", identity.digest),
            )

            for invalid in ("", "sha256:short", "../escape", "sha256:" + "A" * 64):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ManagedProfilePathError, "invalid-workspace-digest"):
                        managed_workspace_profile_path(root / "state", invalid)

    def test_linked_workspace_root_is_rejected_before_identity_is_derived(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            link = root / "link"
            real.mkdir()
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlink unavailable")
            with self.assertRaisesRegex(ManagedProfilePathError, "workspace-root-link-forbidden"):
                verify_workspace_root(link)

    def test_repository_loads_ranked_user_and_managed_layers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            workspace = root / "workspace"
            workspace.mkdir()
            identity = verify_workspace_root(workspace)

            write_profile(
                state / "profiles/personal/user.json",
                scope="personal",
                profile_id="personal:user",
                primary="skill:user-personal",
            )
            write_profile(
                managed_personal_profile_path(state),
                scope="personal",
                profile_id="personal:adaptive-memory",
                primary="skill:managed-personal",
            )
            write_profile(
                workspace / ".codex/workflow-skill-router.json",
                scope="workspace",
                profile_id="workspace:user",
                primary="skill:user-workspace",
            )
            write_profile(
                managed_workspace_profile_path(state, identity.digest),
                scope="workspace",
                profile_id="workspace:adaptive-memory",
                primary="skill:managed-workspace",
            )

            loaded = RoutingProfileRepository(state).load_ranked_layers(
                workspace_root=workspace
            )

            self.assertEqual(
                (
                    ProfileSourceClass.USER_WORKSPACE,
                    ProfileSourceClass.MANAGED_WORKSPACE,
                    ProfileSourceClass.USER_PERSONAL,
                    ProfileSourceClass.MANAGED_PERSONAL,
                ),
                tuple(item.source_class for item in loaded.layers),
            )
            self.assertEqual((), loaded.warnings)
            self.assertEqual(identity.digest, loaded.workspace_identity_digest)

    def test_corrupt_managed_layer_is_skipped_but_corrupt_user_layer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            workspace = root / "workspace"
            workspace.mkdir()
            managed = managed_personal_profile_path(state)
            managed.parent.mkdir(parents=True)
            managed.write_text("{not-json", encoding="utf-8")

            loaded = RoutingProfileRepository(state).load_ranked_layers(
                workspace_root=workspace
            )
            self.assertEqual((), loaded.layers)
            self.assertEqual(("managed-profile-invalid",), loaded.warnings)

            user = state / "profiles/personal/user.json"
            user.parent.mkdir(parents=True, exist_ok=True)
            user.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(RoutingProfileContractError):
                RoutingProfileRepository(state).load_ranked_layers(
                    workspace_root=workspace
                )


    def test_linked_router_data_root_is_rejected_before_managed_profile_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real-state"
            linked = root / "linked-state"
            real.mkdir()
            write_profile(
                managed_personal_profile_path(real),
                scope="personal",
                profile_id="personal:adaptive-memory",
                primary="skill:managed-personal",
            )
            try:
                os.symlink(real, linked, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlink unavailable")
            with self.assertRaisesRegex(RoutingProfileContractError, "link|reparse"):
                RoutingProfileRepository(linked).load_ranked_layers(
                    workspace_root=None
                )

    def test_linked_managed_profile_is_skipped_with_a_sanitized_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            outside = root / "outside.json"
            write_profile(
                outside,
                scope="personal",
                profile_id="personal:adaptive-memory",
                primary="skill:outside",
            )
            target = managed_personal_profile_path(state)
            target.parent.mkdir(parents=True)
            try:
                target.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlink unavailable")
            loaded = RoutingProfileRepository(state).load_ranked_layers(
                workspace_root=None
            )
            self.assertEqual((), loaded.layers)
            self.assertEqual(("managed-profile-invalid",), loaded.warnings)


    def test_managed_file_with_user_owned_identity_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            write_profile(
                managed_personal_profile_path(state),
                scope="personal",
                profile_id="personal:not-adaptive-memory",
                primary="skill:unexpected",
            )
            loaded = RoutingProfileRepository(state).load_ranked_layers(
                workspace_root=None
            )
            self.assertEqual((), loaded.layers)
            self.assertEqual(("managed-profile-invalid",), loaded.warnings)


if __name__ == "__main__":
    unittest.main()
