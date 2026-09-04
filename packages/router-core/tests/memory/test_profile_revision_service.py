from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_skill_router.memory.revisions import ProfileWriteAuthority
from workflow_skill_router.memory.service import WorkflowMemoryService

from memory.test_profile_materializer import prepare_approved


class ProfileRevisionServiceTests(unittest.TestCase):
    def test_service_applies_and_lists_reviewed_profile_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, _, store, _, proposal = prepare_approved(root)
            store.close()
            service = WorkflowMemoryService(fixture.database, data_dir=root)
            authority = ProfileWriteAuthority.router_local_managed(
                "developer", "session-m2c"
            )

            revision = service.apply_profile_update(
                proposal.proposal_id,
                authority=authority,
                expected_state_version=proposal.state_version,
                idempotency_key="service-apply",
                correlation_id="corr-service-apply",
                now="2026-09-04T02:00:00.000Z",
            )
            revisions = service.list_profile_revisions(
                "personal:adaptive-memory"
            )

            self.assertEqual("applied", revision.status)
            self.assertEqual((revision,), revisions)


if __name__ == "__main__":
    unittest.main()
