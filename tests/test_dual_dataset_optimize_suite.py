import unittest
from unittest.mock import patch
from pathlib import Path

from service.chat import commands as cmd


ROOT = Path(__file__).resolve().parents[1]


class DualDatasetOptimizeSuite(unittest.TestCase):
    def test_optimize_code_contains_dual_dataset_resolution_and_summary_keys(self):
        text = (ROOT / "service" / "experiment_optimize.py").read_text(encoding="utf-8")
        self.assertIn("def _resolve_dual_datasets", text)
        self.assertIn('"tuning_dataset": active_tuning_dataset', text)
        self.assertIn('"test_dataset": active_test_dataset', text)
        self.assertIn('"baseline_test_metrics": _avg_metrics', text)
        self.assertIn('"final_test_metrics": _avg_metrics', text)

    @patch("service.chat.commands.MetaLoader.dump")
    @patch("service.chat.commands.TestLoader.load_by_id_file")
    def test_create_experiment_record_dual_dataset(self, mock_load_rows, mock_dump):
        mock_load_rows.return_value = (["text"], [{"text": "a"}])
        data = cmd.create_experiment_record(
            "wf_demo",
            "legacy.csv",
            "graph",
            tuning_dataset="tune.csv",
            test_dataset="test.csv",
        )
        self.assertEqual("test.csv", data.get("dataset"))
        self.assertEqual("tune.csv", data.get("tuning_dataset"))
        self.assertEqual("test.csv", data.get("test_dataset"))
        mock_dump.assert_called_once()

    @patch("service.chat.commands.start_optimize_loop")
    def test_optimize_command_parses_dataset_overrides(self, mock_start):
        mock_start.return_value = "ok"
        out = cmd.execute_slash_command(
            "/optimize exp1 2 tuning=tune.csv test=test.csv",
            session={"pins": {}},
        )
        self.assertEqual("ok", out)
        args, kwargs = mock_start.call_args
        self.assertEqual("exp1", args[0])
        self.assertEqual(2, kwargs.get("max_updates"))
        self.assertEqual("tune.csv", kwargs.get("tuning_dataset"))
        self.assertEqual("test.csv", kwargs.get("test_dataset"))

    def test_experiment_template_and_js_have_dual_dataset_controls(self):
        html = (ROOT / "ui" / "templates" / "experiment.html").read_text(encoding="utf-8")
        js = (ROOT / "ui" / "static" / "js" / "experiment.js").read_text(encoding="utf-8")
        self.assertIn("tuningDatasetSelect", html)
        self.assertIn("autoSplitMode", html)
        self.assertIn("splitSourceSelect", html)
        self.assertIn("test_dataset", js)
        self.assertIn("tuning_dataset", js)
        self.assertIn("split_mode", js)

    def test_optimization_tab_and_flow(self):
        html = (ROOT / "ui" / "templates" / "experiment.html").read_text(encoding="utf-8")
        js = (ROOT / "ui" / "static" / "js" / "experiment.js").read_text(encoding="utf-8")
        opt_py = (ROOT / "service" / "experiment_optimize.py").read_text(encoding="utf-8")
        self.assertIn("expWizardTabs", html)
        self.assertIn("wizard-tab-baseline", html)
        self.assertIn("runBaselineTabBtn", html)
        self.assertIn("runTuningTabBtn", html)
        self.assertIn("runFinalTabBtn", html)
        self.assertIn("optimizationFlowBaseline", html)
        self.assertIn("opt-flow-run-btn", js)
        self.assertIn("showWizardTab", js)
        self.assertIn("runnerAgentRoster", html)
        self.assertIn("renderRunnerAgentRoster", js)
        self.assertIn("runner-agents", js)
        self.assertIn("wizard-tab-config", html)
        self.assertNotIn('href="#optimization"', html)
        self.assertIn("Configuration &amp; Preview", html)
        self.assertIn("renderOptimizationFlow", js)
        self.assertIn("baseline-test-report", js)
        self.assertIn("def generate_baseline_test_report", opt_py)
        self.assertIn("def init_optimization_flow_steps", opt_py)
        self.assertIn("report_baseline_test.md", opt_py)
        self.assertIn("report_optimized_test.md", opt_py)
        self.assertIn("def _write_text(path: Path | str", opt_py)


if __name__ == "__main__":
    unittest.main()
