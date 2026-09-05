from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.profiles.contract import decode_routing_profile
from workflow_skill_router.profiles.layers import (
    LayeredRoutingProfile,
    ProfileSourceClass,
)
from workflow_skill_router.profiles.resolver import (
    RoutingMatchContext,
    resolve_layered_profile_route,
)

if __package__:
    from .test_contract import profile_document
else:
    from test_contract import profile_document


DIGEST = "sha256:" + "a" * 64


def layered(
    source: ProfileSourceClass,
    *,
    primary: str,
    priority: int,
    profile_name: str,
) -> LayeredRoutingProfile:
    scope = "workspace" if "workspace" in source.value else "personal"
    document = profile_document(scope=scope)
    document["profile_id"] = f"{scope}:{profile_name}"
    document["rules"][0]["priority"] = priority
    document["rules"][0]["route"]["skill_tree"][0]["primary_skill_id"] = primary
    profile = decode_routing_profile(document)
    return LayeredRoutingProfile(
        profile=profile,
        source_class=source,
        source_digest=profile.profile_digest,
        workspace_identity_digest=(DIGEST if scope == "workspace" else None),
    )


class ProfileLayerTests(unittest.TestCase):
    def test_source_class_contract_rejects_scope_and_digest_mismatch(self) -> None:
        personal = decode_routing_profile(profile_document(scope="personal"))
        workspace = decode_routing_profile(profile_document(scope="workspace"))

        with self.assertRaisesRegex(ValueError, "profile-layer-scope-mismatch"):
            LayeredRoutingProfile(
                personal,
                ProfileSourceClass.USER_WORKSPACE,
                personal.profile_digest,
                DIGEST,
            )
        with self.assertRaisesRegex(ValueError, "profile-layer-workspace-digest-required"):
            LayeredRoutingProfile(
                workspace,
                ProfileSourceClass.MANAGED_WORKSPACE,
                workspace.profile_digest,
                None,
            )
        with self.assertRaisesRegex(ValueError, "profile-layer-source-digest-mismatch"):
            LayeredRoutingProfile(
                personal,
                ProfileSourceClass.MANAGED_PERSONAL,
                "sha256:" + "b" * 64,
                None,
            )

    def test_fixed_owner_precedence_beats_rule_priority_and_input_order(self) -> None:
        layers = (
            layered(
                ProfileSourceClass.MANAGED_PERSONAL,
                primary="skill:managed-personal",
                priority=1000,
                profile_name="managed-personal",
            ),
            layered(
                ProfileSourceClass.USER_PERSONAL,
                primary="skill:user-personal",
                priority=-1000,
                profile_name="user-personal",
            ),
            layered(
                ProfileSourceClass.MANAGED_WORKSPACE,
                primary="skill:managed-workspace",
                priority=1000,
                profile_name="managed-workspace",
            ),
            layered(
                ProfileSourceClass.USER_WORKSPACE,
                primary="skill:user-workspace",
                priority=-1000,
                profile_name="user-workspace",
            ),
        )

        for ordered in (layers, tuple(reversed(layers))):
            with self.subTest(order=[item.source_class.value for item in ordered]):
                result = resolve_layered_profile_route(
                    ordered,
                    objective="Deliver the API",
                    default_work_mode="phased",
                    context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
                )
                self.assertIsNotNone(result)
                self.assertEqual("workspace-profile", result.route_source)
                self.assertEqual("workspace:user-workspace", result.profile_id)
                self.assertEqual(
                    "skill:user-workspace",
                    result.current_phase.primary_skill_id,
                )

    def test_each_managed_layer_has_an_explicit_public_route_source(self) -> None:
        managed_workspace = layered(
            ProfileSourceClass.MANAGED_WORKSPACE,
            primary="skill:managed-workspace",
            priority=1,
            profile_name="managed-workspace",
        )
        managed_personal = layered(
            ProfileSourceClass.MANAGED_PERSONAL,
            primary="skill:managed-personal",
            priority=1,
            profile_name="managed-personal",
        )

        workspace_result = resolve_layered_profile_route(
            (managed_workspace, managed_personal),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )
        personal_result = resolve_layered_profile_route(
            (managed_personal,),
            objective="API delivery",
            default_work_mode="phased",
            context=RoutingMatchContext(domains=("api",), tags=("delivery",)),
        )

        self.assertEqual("managed-workspace-profile", workspace_result.route_source)
        self.assertEqual("managed-personal-profile", personal_result.route_source)


if __name__ == "__main__":
    unittest.main()
