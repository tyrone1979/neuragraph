import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkflowMetricsSuite(unittest.TestCase):
    def test_relation_pairs_preserves_eval_agent_f1(self):
        from utils.workflow_metrics import compute_workflow_metrics

        row = {
            "gold_relations": "tacrolimus | CID | IDDM",
            "entities": json.dumps(
                [
                    {"text": "tacrolimus", "id": "D016559", "label": "Chemical"},
                    {"text": "IDDM", "id": "D003922", "label": "Disease"},
                ]
            ),
        }
        state = {
            "relations": ["D016559 | CID | D003922"],
            "entities": row["entities"],
            "metrics": {
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "tp": 1,
                "fp": 0,
                "fn": 0,
            },
        }
        out = compute_workflow_metrics("wf_re_pubtator_dev10", row, state)
        self.assertAlmostEqual(out["f1"], 1.0)
        self.assertAlmostEqual(out["tp"], 1.0)
        self.assertIn("rel_f1", out)

    def test_relation_pairs_normalizes_without_eval_agent(self):
        from utils.workflow_metrics import compute_workflow_metrics

        row = {
            "gold_relations": "tacrolimus | CID | IDDM",
            "entities": json.dumps(
                [
                    {"text": "tacrolimus", "id": "D016559", "label": "Chemical"},
                    {"text": "IDDM", "id": "D003922", "label": "Disease"},
                ]
            ),
        }
        state = {
            "relations": ["D016559 | CID | D003922"],
            "entities": row["entities"],
        }
        out = compute_workflow_metrics("wf_re_pubtator_dev10", row, state)
        self.assertAlmostEqual(out["f1"], 1.0)
        self.assertAlmostEqual(out.get("rel_tp", out.get("tp")), 1.0)

    def test_cdr_txt_rows_include_gold_relations(self):
        from service.entity.test import TestLoader

        _fields, rows = TestLoader.load_by_id_file("wf_e2e_pubtator_re", "test.txt")
        self.assertTrue(rows)
        self.assertIn("gold_relations", rows[0])
        self.assertIn("CID", rows[0]["gold_relations"])

    def test_empty_relation_sets_do_not_crash_metrics(self):
        from plugin.plugin_loader import get_plugin

        calc = get_plugin("MetricsCalculation")
        out = calc.calculate([], [])
        self.assertEqual(out["tp"], 0)
        self.assertEqual(out["fn"], 0)

    def test_missing_gold_skips_workflow_metrics(self):
        from utils.workflow_metrics import compute_workflow_metrics

        row = {"text": "sample", "gold_relations": "", "entities": "[]"}
        state = {"relations": ["D001 | D002"]}
        out = compute_workflow_metrics("wf_re_pubtator_dev10", row, state)
        self.assertEqual(out, {})

    def test_empty_entity_dict_metrics_do_not_crash(self):
        from plugin.plugin_loader import get_plugin

        calc = get_plugin("MetricsCalculation")
        out = calc.calculate({}, {})
        self.assertEqual(out["tp"], 0)
        self.assertEqual(out["fp"], 0)
        self.assertEqual(out["fn"], 0)


if __name__ == "__main__":
    unittest.main()
