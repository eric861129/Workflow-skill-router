from datetime import datetime, timezone
import unittest

from workflow_skill_router.evaluation.attestation import ReviewVerifierRegistry
from workflow_skill_router.evaluation.reporting import build_review_draft, publish_sanitized


class ReportingTests(unittest.TestCase):
    def test_draft_redacts_secrets_and_local_paths(self):
        draft = build_review_draft({"api_key": "secret", "trace": r"C:\Users\user\trace.json"}, "behavior")
        self.assertEqual("[REDACTED]", draft.summary["api_key"])
        self.assertNotIn("Users", draft.summary["trace"])

    def test_publication_rejects_without_human_verifier(self):
        draft = build_review_draft({"pass_rate": 1.0}, "behavior")
        with self.assertRaisesRegex(PermissionError, "human_review_attestation_invalid"):
            publish_sanitized(draft, "human", "self-asserted", ReviewVerifierRegistry(),
                              datetime.now(timezone.utc))


if __name__ == "__main__": unittest.main()
