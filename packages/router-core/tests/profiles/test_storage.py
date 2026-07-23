from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.profiles.contract import RoutingProfileContractError
from workflow_skill_router.profiles.storage import (
    MAX_PERSONAL_PROFILE_FILES,
    RoutingProfileRepository,
    default_router_data_dir,
)

if __package__:
    from .test_contract import profile_document
else:
    from test_contract import profile_document


class RoutingProfileStorageTests(unittest.TestCase):
    @staticmethod
    def _create_directory_link(link: Path, target: Path) -> None:
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise OSError(completed.stderr or completed.stdout)
            return
        link.symlink_to(target, target_is_directory=True)

    def test_default_data_paths_match_the_plugin_on_each_platform(self) -> None:
        self.assertEqual(
            Path("C:/Local/Codex/workflow-skill-router"),
            default_router_data_dir(
                platform="win32",
                environment={"LOCALAPPDATA": "C:/Local"},
                home=Path("C:/Users/demo"),
            ),
        )
        self.assertEqual(
            Path("/Users/demo/Library/Application Support/Codex/workflow-skill-router"),
            default_router_data_dir(platform="darwin", environment={}, home=Path("/Users/demo")),
        )
        self.assertEqual(
            Path("/state/codex/workflow-skill-router"),
            default_router_data_dir(
                platform="linux",
                environment={"XDG_STATE_HOME": "/state"},
                home=Path("/home/demo"),
            ),
        )

    def test_installs_and_loads_personal_profiles_outside_the_plugin_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_text(json.dumps(profile_document(), ensure_ascii=False), encoding="utf-8")
            repository = RoutingProfileRepository(root / "state")

            installed = repository.install_personal(source)
            loaded = repository.load_layers(workspace_root=None)

            self.assertEqual(
                (root / "state/profiles/personal/api-delivery.json").resolve(),
                installed,
            )
            self.assertEqual(("personal:api-delivery",), tuple(item.profile_id for item in loaded))
            self.assertNotIn("plugins", installed.parts)

    def test_workspace_profile_uses_one_fixed_non_symlink_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            profile_path = workspace / ".codex/workflow-skill-router.json"
            profile_path.parent.mkdir(parents=True)
            profile_path.write_text(
                json.dumps(profile_document(scope="workspace"), ensure_ascii=False),
                encoding="utf-8",
            )

            loaded = RoutingProfileRepository(root / "state").load_layers(
                workspace_root=workspace
            )

            self.assertEqual(("workspace:api-delivery",), tuple(item.profile_id for item in loaded))

    def test_invalid_existing_profile_fails_closed_instead_of_being_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_dir = root / "state/profiles/personal"
            profile_dir.mkdir(parents=True)
            (profile_dir / "broken.json").write_text("{}", encoding="utf-8")

            with self.assertRaises(RoutingProfileContractError):
                RoutingProfileRepository(root / "state").load_layers(workspace_root=None)

    def test_install_rejects_a_new_profile_after_the_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = RoutingProfileRepository(root / "state")
            repository.personal_dir.mkdir(parents=True)
            for index in range(MAX_PERSONAL_PROFILE_FILES):
                document = profile_document()
                document["profile_id"] = f"personal:profile-{index}"
                (repository.personal_dir / f"profile-{index}.json").write_text(
                    json.dumps(document),
                    encoding="utf-8",
                )
            source = root / "new.json"
            document = profile_document()
            document["profile_id"] = "personal:new-profile"
            source.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(RoutingProfileContractError, "file count"):
                repository.install_personal(source)

            self.assertFalse((repository.personal_dir / "new-profile.json").exists())

    def test_duplicate_personal_profile_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_dir = root / "state/profiles/personal"
            profile_dir.mkdir(parents=True)
            document = profile_document()
            (profile_dir / "first.json").write_text(json.dumps(document), encoding="utf-8")
            (profile_dir / "second.json").write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(RoutingProfileContractError, "profile_id"):
                RoutingProfileRepository(root / "state").list_personal()

    def test_dangling_workspace_profile_link_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repo"
            profile_path = workspace / ".codex/workflow-skill-router.json"
            profile_path.parent.mkdir(parents=True)
            try:
                profile_path.symlink_to(root / "missing-profile.json")
            except OSError as error:
                self.skipTest(f"symlink creation is unavailable: {error}")

            with self.assertRaisesRegex(RoutingProfileContractError, "link"):
                RoutingProfileRepository(root / "state").load_layers(
                    workspace_root=workspace
                )

    def test_install_rejects_a_linked_profiles_directory_before_writing_outside(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "state"
            outside = root / "outside"
            data_dir.mkdir()
            outside.mkdir()
            self._create_directory_link(data_dir / "profiles", outside)
            source = root / "source.json"
            source.write_text(json.dumps(profile_document()), encoding="utf-8")

            with self.assertRaisesRegex(RoutingProfileContractError, "link|reparse"):
                RoutingProfileRepository(data_dir).install_personal(source)

            self.assertFalse((outside / "personal").exists())

    def test_install_rejects_a_profile_source_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text(json.dumps(profile_document()), encoding="utf-8")
            source = root / "source.json"
            try:
                source.symlink_to(target)
            except OSError as error:
                self.skipTest(f"file symlink creation is unavailable: {error}")

            with self.assertRaisesRegex(RoutingProfileContractError, "non-link"):
                RoutingProfileRepository(root / "state").install_personal(source)


if __name__ == "__main__":
    unittest.main()
