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

    def test_report_view_uses_inline_chart_layout(self):
        html = (ROOT / "ui" / "templates" / "experiment.html").read_text(encoding="utf-8")
        js = (ROOT / "ui" / "static" / "js" / "experiment.js").read_text(encoding="utf-8")
        css = (ROOT / "ui" / "static" / "css" / "exp.css").read_text(encoding="utf-8")
        self.assertNotIn("reportChartsSection", html)
        self.assertIn("report-inline-chart-card", js)
        self.assertIn("report-inline-chart-canvas", css)


if __name__ == "__main__":
    unittest.main()
