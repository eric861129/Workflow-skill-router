import unittest

from workflow_skill_router.evaluation.adapters import select_execution_adapter


class AdapterTests(unittest.TestCase):
    def test_behavior_without_automation_is_manual_required(self):
        selected = select_execution_adapter([], "behavior")
        self.assertEqual("manual-import", selected.kind)
        self.assertEqual("manual-required", selected.status)

    def test_contract_does_not_claim_real_model_execution(self):
        selected = select_execution_adapter([], "contract")
        self.assertEqual("contract", selected.kind)
        self.assertEqual("tier-0-contract", selected.evidence_class)

    def test_verified_fresh_host_task_is_preferred(self):
        selected = select_execution_adapter(["external:fresh-session", "host:fresh-task"], "outcome")
        self.assertEqual("host-task", selected.kind)
        self.assertEqual("scheduled", selected.status)


if __name__ == "__main__": unittest.main()
