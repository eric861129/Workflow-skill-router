from __future__ import annotations

import unittest

from workflow_skill_router.runtime_readiness import RUNTIME_READINESS
from workflow_skill_router.service_codecs import build_service_codec_registry
from workflow_skill_router.tool_dispatch import PUBLIC_TOOLS


class MemorySurfaceInventoryTests(unittest.TestCase):
    def test_public_surface_contains_exactly_twenty_tools(self):
        self.assertEqual(20, len(PUBLIC_TOOLS))
        self.assertEqual(set(PUBLIC_TOOLS), set(RUNTIME_READINESS))
        self.assertEqual(set(PUBLIC_TOOLS), set(build_service_codec_registry()))
        self.assertTrue({
            "get_memory_status", "remember_workflow", "record_route_feedback",
            "list_workflow_candidates", "preview_profile_update",
            "transition_profile_update", "rollback_profile_revision",
            "purge_workflow_memory",
        }.issubset(PUBLIC_TOOLS))
