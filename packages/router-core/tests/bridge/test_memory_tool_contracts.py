from __future__ import annotations

import copy
import unittest

from workflow_skill_router.runtime_readiness import RUNTIME_READINESS
from workflow_skill_router.service_codecs import ServiceCodecError, build_service_codec_registry
from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS


MEMORY_TOOLS = (
    "get_memory_status", "remember_workflow", "record_route_feedback",
    "list_workflow_candidates", "preview_profile_update", "transition_profile_update",
    "rollback_profile_revision", "purge_workflow_memory",
)
CONTEXT = {"session_id": "session-memory", "actor": "developer", "runtime_policy_snapshot_id": "policy-memory"}
DIGEST = "sha256:" + "a" * 64
MUTATION = {"idempotency_key": "memory-test", "correlation_id": "memory-correlation"}
SAMPLES = {
    "get_memory_status": {"context": CONTEXT, "workspace_root": None},
    "remember_workflow": {"context": CONTEXT, "workspace_root": None, "workflow_run_id": "workflow:test", "target_profile_class": "managed-personal", "risk_class": "r1", "side_effect_outcome": "none", "one_shot": "remember-once", **MUTATION},
    "record_route_feedback": {"context": CONTEXT, "workspace_root": None, "workflow_run_id": "workflow:test", "observation_id": "observation:" + "a" * 32, "feedback_type": "accepted", "reason_code": "user-accepted", "correction_dimensions": [], "original_route_digest": None, "corrected_route_digest": None, **MUTATION},
    "list_workflow_candidates": {"context": CONTEXT, "workspace_root": None, "status": None, "limit": 100},
    "preview_profile_update": {"context": CONTEXT, "workspace_root": None, "candidate_id": "candidate:" + "a" * 32},
    "transition_profile_update": {"context": CONTEXT, "workspace_root": None, "proposal_id": "proposal:" + "a" * 32, "expected_proposal_digest": DIGEST, "expected_profile_digest": "missing", "action": "approve", "expected_state_version": 1, **MUTATION},
    "rollback_profile_revision": {"context": CONTEXT, "workspace_root": None, "source_revision_id": "revision:" + "a" * 32, "expected_profile_digest": DIGEST, **MUTATION},
    "purge_workflow_memory": {"context": CONTEXT, "scope": "history-only", "expected_summary_digest": DIGEST, "include_managed_profiles": False, "confirmed": True, **MUTATION},
}


class MemoryToolContractTests(unittest.TestCase):
    def codec(self, name):
        registry = build_service_codec_registry()
        self.assertIn(name, registry, "M4-A typed codec is missing")
        return registry[name]

    def test_exact_twenty_tool_parity(self):
        self.assertEqual(20, len(PUBLIC_TOOLS))
        self.assertEqual(set(PUBLIC_TOOLS), set(RUNTIME_READINESS))
        self.assertEqual(set(PUBLIC_TOOLS), set(build_service_codec_registry()))
        self.assertTrue(set(MEMORY_TOOLS) <= set(PUBLIC_TOOLS))

    def test_memory_readiness_preserves_conditional_write_authority(self):
        for name in MEMORY_TOOLS:
            with self.subTest(tool=name):
                self.assertIn(name, RUNTIME_READINESS)
                expected = "conditional-local" if name in {"transition_profile_update", "rollback_profile_revision"} else "local-ready"
                self.assertEqual(expected, RUNTIME_READINESS[name].availability)
                risk = "R1" if name in {"transition_profile_update", "rollback_profile_revision", "purge_workflow_memory"} else "R0"
                self.assertEqual(risk, RUNTIME_READINESS[name].risk_class)

    def test_valid_commands_are_typed_and_unknown_fields_are_rejected(self):
        for name, arguments in SAMPLES.items():
            with self.subTest(tool=name):
                codec = self.codec(name)
                command = codec.decode(arguments)
                self.assertEqual("session-memory", command.context.session_id)
                with self.assertRaises(ServiceCodecError):
                    codec.decode({**arguments, "profile_content": {"rules": []}})
                wrong = copy.deepcopy(arguments)
                wrong["context"]["trusted"] = True
                with self.assertRaises(ServiceCodecError):
                    codec.decode(wrong)

    def test_transition_cannot_replace_bound_content_or_authority(self):
        codec = self.codec("transition_profile_update")
        for field in ("candidate_id", "target_profile_class", "profile", "diff", "matcher_seed", "authority", "target_path"):
            with self.subTest(field=field), self.assertRaises(ServiceCodecError):
                codec.decode({**SAMPLES["transition_profile_update"], field: "replacement"})

    def test_invalid_enums_digests_and_boolean_versions_fail_closed(self):
        cases = (
            ("remember_workflow", "target_profile_class", "arbitrary-file"),
            ("remember_workflow", "risk_class", "r4"),
            ("remember_workflow", "workspace_root", {}),
            ("record_route_feedback", "feedback_type", "activate"),
            ("list_workflow_candidates", "status", "anything"),
            ("list_workflow_candidates", "limit", True),
            ("list_workflow_candidates", "limit", 1001),
            ("preview_profile_update", "candidate_id", "candidate:bad"),
            ("transition_profile_update", "expected_state_version", True),
            ("transition_profile_update", "expected_state_version", 0),
            ("transition_profile_update", "expected_proposal_digest", "sha256:"),
            ("transition_profile_update", "action", "force"),
            ("purge_workflow_memory", "confirmed", False),
            ("purge_workflow_memory", "scope", "everything"),
        )
        for name, field, value in cases:
            with self.subTest(tool=name, field=field), self.assertRaises(ServiceCodecError):
                self.codec(name).decode({**SAMPLES[name], field: value})

    def test_free_text_feedback_and_model_matchers_are_not_public_inputs(self):
        for name, field in (("remember_workflow", "matcher_seed"), ("record_route_feedback", "free_text")):
            with self.subTest(tool=name), self.assertRaises(ServiceCodecError):
                self.codec(name).decode({**SAMPLES[name], field: "raw objective or secret"})
