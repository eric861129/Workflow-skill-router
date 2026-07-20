import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "starter" / "v2" / "workflow-skill-router"
TARGET = ROOT / "plugins" / "workflow-skill-router" / "skills" / "workflow-skill-router"
SKILL_FILES = (
    Path("SKILL.md"),
    Path("assets/personal-routing-profile.example.json"),
    Path("assets/workspace-routing-profile.example.json"),
    Path("references/evaluation-boundary.md"),
    Path("references/goal-protocol.md"),
    Path("references/personal-routing-profiles.md"),
    Path("references/routing-protocol.md"),
)


class SkillSourceSyncTests(unittest.TestCase):
    def test_plugin_skill_is_byte_identical_to_the_canonical_starter(self) -> None:
        actual = tuple(
            sorted(path.relative_to(TARGET) for path in TARGET.rglob("*") if path.is_file())
        )
        self.assertEqual(tuple(sorted(SKILL_FILES)), actual)
        for relative in SKILL_FILES:
            self.assertEqual(
                (SOURCE / relative).read_bytes(),
                (TARGET / relative).read_bytes(),
                relative.as_posix(),
            )

    def test_canonical_skill_states_the_consent_and_reporting_contract(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        combined = skill + "\n" + protocol
        self.assertIn("未指定 SKILL", combined)
        self.assertIn("不為 Router 自己推薦的輔助 SKILL 額外詢問同意", combined)
        self.assertIn("使用者指定 SKILL", combined)
        self.assertIn("新增推薦支援前必須取得 scoped consent", combined)
        self.assertIn("執行前宣告預計使用的 SKILL", combined)
        self.assertIn("完成後列出實際使用的 SKILL", combined)

    def test_canonical_skill_defines_generic_capability_mapping_contract(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        combined = skill + "\n" + protocol
        self.assertIn("description、domains、stages、availability", combined)
        self.assertIn("目前決策瓶頸", combined)
        self.assertIn("第一個可執行 Phase", combined)
        self.assertIn("`availability` 是 activation gate", combined)
        self.assertIn("保留 intended SKILL", combined)
        self.assertIn("不得把 workflow-skill-router 自己當成預設 Primary", combined)

    def test_canonical_skill_scopes_support_to_current_execution_boundary(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        routing = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        goal = (SOURCE / "references/goal-protocol.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, routing, goal))

        self.assertIn("目前 Phase 與 immediate exit gate", combined)
        self.assertIn("未來 Phase 的能力不得提前列入目前 support_skills", combined)
        self.assertIn("未來 Work Item 的 SKILL 只能記在計畫", combined)
        self.assertIn("進入該 Work Item 時重新路由", combined)

    def test_canonical_skill_gives_deterministic_phase_goal_and_unavailable_recipes(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        routing = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        goal = (SOURCE / "references/goal-protocol.md").read_text(encoding="utf-8")
        combined = "\n".join((skill, routing, goal))

        self.assertIn("目前 route = 目前 Phase Primary + immediate exit gate support", combined)
        self.assertIn("Phase transition 後建立新 route", combined)
        self.assertIn("Goal 規劃 Work Item", combined)
        self.assertIn("fallback 不得改寫 primary_skill 或塞入 support_skills", combined)

    def test_canonical_skill_distinguishes_exit_gate_definition_from_support_activation(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        routing = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, routing))

        self.assertIn(
            "只有必須在目前 Phase 結束前實際啟用的能力，才可列入 support_skills",
            combined,
        )
        self.assertIn(
            "定義、描述或規劃 exit evidence 不等於啟用 verification SKILL",
            combined,
        )
        self.assertIn(
            "若 Primary 能自行完成目前 Phase 與 exit gate 定義，support_skills 必須為空",
            combined,
        )

    def test_canonical_skill_defines_consent_transition_output_shape(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        routing = (SOURCE / "references/routing-protocol.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, routing))

        self.assertIn(
            "`proposal-required` 時，support_skills 必須列出具體提案集合",
            combined,
        )
        self.assertIn(
            "這些項目在 `approved` 前只是 proposed，不是 activated",
            combined,
        )
        self.assertIn("`approved` 時保留相同 support_skills", combined)
        self.assertIn("`rejected` 時清空 support_skills", combined)

    def test_canonical_skill_preserves_user_owned_skill_tree_customization(self) -> None:
        skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        profiles = (SOURCE / "references/personal-routing-profiles.md").read_text(
            encoding="utf-8"
        )
        combined = skill + "\n" + profiles

        for marker in (
            "Personal Routing Profile",
            ".codex/workflow-skill-router.json",
            "workspace profile > personal profile > built-in",
            "使用者當次明確指定 SKILL",
            "Runtime Capability Discovery",
            "intended-unverified",
            "skill-only-fallback",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_profile_example_is_a_strict_non_executable_skill_tree(self) -> None:
        import json

        profile = json.loads(
            (SOURCE / "assets/personal-routing-profile.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("workflow-skill-router/routing-profile", profile["schema_id"])
        self.assertEqual("personal", profile["scope"])
        self.assertNotIn("instructions", profile)
        self.assertTrue(all(
            len(phase["support_skill_ids"]) <= 3
            for rule in profile["rules"]
            for phase in rule["route"]["skill_tree"]
        ))

        workspace = json.loads(
            (SOURCE / "assets/workspace-routing-profile.example.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("workspace:api-delivery", workspace["profile_id"])
        self.assertEqual("workspace", workspace["scope"])
        self.assertNotIn("instructions", workspace)

if __name__ == "__main__":
    unittest.main()
