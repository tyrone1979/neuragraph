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


if __name__ == "__main__":
    unittest.main()
