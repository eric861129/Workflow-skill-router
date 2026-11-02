from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.routing.directives import (  # noqa: E402
    DirectiveAmbiguityError,
    canonical_explicit_skill_id,
    resolve_directive,
)
from workflow_skill_router.routing.models import DirectiveInput  # noqa: E402


class ExplicitSkillIdCanonicalizationTests(unittest.TestCase):
    def test_bare_skill_name_gets_the_skill_prefix(self) -> None:
        # A Host user names a Skill the way the Host lists it; the Router stores the canonical id.
        self.assertEqual("skill:python-test-writer", canonical_explicit_skill_id("python-test-writer"))
        self.assertEqual("skill:workflow-skill-router:foo", canonical_explicit_skill_id("workflow-skill-router:foo"))

    def test_canonical_ids_pass_through_unchanged(self) -> None:
        self.assertEqual("skill:api-designer", canonical_explicit_skill_id("skill:api-designer"))

    def test_other_forms_are_rejected_with_a_public_reason(self) -> None:
        for value in ("Bad Name", "", "skill:", "/etc/passwd", "a" * 200):
            with self.subTest(value=value):
                with self.assertRaises(DirectiveAmbiguityError) as caught:
                    canonical_explicit_skill_id(value)
                self.assertEqual("explicit-skill-id-not-canonical", caught.exception.reason)
                self.assertNotIn(value or "<empty>", caught.exception.reason)

    def test_resolve_directive_canonicalizes_and_deduplicates(self) -> None:
        directive = resolve_directive(DirectiveInput(
            text="add a regression test",
            explicit_skill_ids=("python-test-writer", " skill:python-test-writer ", "skill:docs-writer"),
            skill_semantics_hint="use",
        ))
        self.assertEqual(("skill:python-test-writer", "skill:docs-writer"), directive.explicit_skills)

    def test_resolve_directive_rejects_before_reading_semantics(self) -> None:
        with self.assertRaises(DirectiveAmbiguityError) as caught:
            resolve_directive(DirectiveInput(text="t", explicit_skill_ids=("Bad Name",), skill_semantics_hint=None))
        self.assertEqual("explicit-skill-id-not-canonical", caught.exception.reason)

    def test_other_directive_errors_keep_the_default_reason(self) -> None:
        with self.assertRaises(DirectiveAmbiguityError) as caught:
            resolve_directive(DirectiveInput(text="t", explicit_skill_ids=("skill:a", "skill:b"), skill_semantics_hint=None))
        self.assertEqual("directive-ambiguous", caught.exception.reason)


if __name__ == "__main__":
    unittest.main()
