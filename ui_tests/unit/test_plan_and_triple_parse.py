"""Unit tests for plan_json and relation triple parsers."""
import json
import unittest

from utils.conversion import parse_plan_json, parse_relation_triples


class PlanAndTripleParseTest(unittest.TestCase):
    def test_plan_json_from_prose_defaults_empty(self):
        prose = "No actionable FN/FP evidence in this package."
        parsed = parse_plan_json(prose)
        self.assertEqual(parsed, {"modifications": []})

    def test_plan_json_from_codeblock(self):
        raw = 'Here is the plan:\n```json\n{"modifications": [{"target_agent_id": "a1"}]}\n```'
        parsed = parse_plan_json(raw)
        self.assertEqual(len(parsed["modifications"]), 1)

    def test_relation_triples_pipe_lines(self):
        raw = "Aspirin | treats | pain\n"
        self.assertEqual(parse_relation_triples(raw), ["Aspirin | treats | pain"])

    def test_relation_triples_ignores_none(self):
        self.assertEqual(parse_relation_triples("NONE\n"), [])


if __name__ == "__main__":
    unittest.main()
