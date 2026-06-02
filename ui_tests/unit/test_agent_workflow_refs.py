"""Tests for agent workflow reference counting."""

import unittest

from utils.graphutils import count_agent_workflow_references


class AgentWorkflowRefsSuite(unittest.TestCase):
    def test_returns_int_counts(self):
        counts = count_agent_workflow_references()
        self.assertIsInstance(counts, dict)
        for agent_id, value in counts.items():
            self.assertIsInstance(agent_id, str)
            self.assertIsInstance(value, int)
            self.assertGreaterEqual(value, 0)

    def test_pubtator_eval_agents_are_referenced(self):
        counts = count_agent_workflow_references()
        self.assertGreaterEqual(counts.get("relation_extract_pubtator", 0), 1)
        self.assertGreaterEqual(counts.get("eval_metrics_relation", 0), 1)


if __name__ == "__main__":
    unittest.main()
