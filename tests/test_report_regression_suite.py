import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReportRegressionSuite(unittest.TestCase):
    def test_report_prompts_avoid_hardcoded_keyword_logic(self):
        for name in ("report_experiment.json", "report_experiment_tool.json"):
            p = ROOT / "meta" / "agents" / name
            data = json.loads(p.read_text(encoding="utf-8"))
            human = str((data.get("prompt_template") or {}).get("human") or "")
            self.assertIn("Do not hardcode special handling", human)
            self.assertIn("Do not apply fixed keyword-triggered heuristics", human)
            self.assertIn("NEVER suggest full-text keyword", human)
            self.assertIn("normalize_cid_lines", human)
            self.assertIn("filtered_entities", human)
            self.assertIn("character position", human)

    def test_refiner_prompt_rejects_label_and_position_shortcuts(self):
        data = json.loads(
            (ROOT / "meta" / "agents" / "agent_refiner.json").read_text(encoding="utf-8")
        )
        human = str((data.get("prompt_template") or {}).get("human") or "")
        self.assertIn("filtered_entities", human)
        self.assertIn("head_pos", human)
        self.assertIn("causal_keywords", human)
        self.assertIn("normalize_cid_lines", human)

    def test_filter_disallowed_modifications(self):
        from service.optimize_suggestion_filter import (
            disallowed_modification_reason,
            filter_disallowed_modifications,
        )

        gold_mod = {
            "target_agent_id": "relation_result_to_id_pair",
            "process_append": (
                "entities = state.get('filtered_entities', []); "
                "head_type = next((e.get('label') for e in entities if e.get('id') == hid), '')"
            ),
        }
        pos_mod = {
            "target_agent_id": "relation_result_to_id_pair",
            "process_append": (
                "head_pos = text.find(state.get('head', '')); "
                "if head_pos > tail_pos: __result__ = []"
            ),
        }
        kw_mod = {
            "target_agent_id": "relation_extract_pubtator",
            "process_append": (
                "causal_keywords = ['induced', 'caused']; "
                "if not any(kw in text_lower for kw in causal_keywords): __result__ = []"
            ),
        }
        ok_mod = {
            "target_agent_id": "relation_llm",
            "prompt_human_append": "Only output $ when the sentence states direct drug-induced disease causation.",
        }
        self.assertIn("filtered_entities", disallowed_modification_reason(gold_mod))
        self.assertIn("position-only", disallowed_modification_reason(pos_mod))
        self.assertIn("keyword filter", disallowed_modification_reason(kw_mod))
        self.assertEqual("", disallowed_modification_reason(ok_mod))
        kept, rejected = filter_disallowed_modifications([gold_mod, pos_mod, kw_mod, ok_mod])
        self.assertEqual(1, len(kept))
        self.assertEqual(3, len(rejected))

    def test_report_view_uses_inline_chart_layout(self):
        html = (ROOT / "ui" / "templates" / "experiment.html").read_text(encoding="utf-8")
        js = (ROOT / "ui" / "static" / "js" / "experiment.js").read_text(encoding="utf-8")
        css = (ROOT / "ui" / "static" / "css" / "exp.css").read_text(encoding="utf-8")
        self.assertNotIn("reportChartsSection", html)
        self.assertIn("experimentResultsAccordion", html)
        self.assertIn("report-inline-chart-card", js)
        self.assertIn("report-inline-chart-canvas", css)


if __name__ == "__main__":
    unittest.main()
