import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service.result.loader import (
    ResultLoader,
    REPORT_CHART_SAMPLE_THRESHOLD,
    REPORT_EXEMPLAR_MAX,
    REPORT_EXEMPLAR_TOP_FP,
    REPORT_EXEMPLAR_TOP_FN,
    build_report_payload_states,
    compact_sample_for_storage,
    compact_states_for_report,
    load_states_for_report,
    select_fp_fn_exemplars,
    summarize_experiment_metrics,
    write_states_bundle,
)


def _fake_states(n: int, *, text_len: int = 5000) -> dict:
    out = {}
    for i in range(1, n + 1):
        out[str(i)] = {
            "metrics": {
                "precision": 0.8,
                "recall": 0.7,
                "f1": 0.75 - (i * 0.01),
                "tp": 2,
                "fp": i % 7,
                "fn": (n - i) % 5,
            },
            "text": "x" * text_len,
            "entities": {"Chemical": ["aspirin"], "Disease": ["pain"]},
            "sentences": ["a", "b"],
        }
    return out


class ReportStatesCompactTest(unittest.TestCase):
    def test_large_run_uses_charts_mode(self):
        states = _fake_states(REPORT_CHART_SAMPLE_THRESHOLD + 5)
        compact = compact_states_for_report(states)
        self.assertEqual("charts", compact.get("report_mode"))
        self.assertEqual(REPORT_CHART_SAMPLE_THRESHOLD + 5, compact.get("sample_count"))
        self.assertIn("metrics_summary", compact)
        self.assertIn("chart_series", compact)
        self.assertNotIn("1", compact)

    def test_large_run_examples_detail_not_truncated(self):
        states = _fake_states(30, text_len=8000)
        compact = compact_states_for_report(states)
        detail = compact.get("examples_detail") or {}
        self.assertGreater(len(detail), 0)
        for sid, sample in detail.items():
            self.assertEqual(8000, len(sample.get("text", "")))
            self.assertIn("entities", sample)

    def test_exemplars_rank_by_fp_and_fn(self):
        rows = [
            {"sample_id": 1, "f1": 0.9, "tp": 10, "fp": 1, "fn": 0},
            {"sample_id": 2, "f1": 0.5, "tp": 2, "fp": 9, "fn": 1},
            {"sample_id": 3, "f1": 0.6, "tp": 3, "fp": 2, "fn": 8},
            {"sample_id": 4, "f1": 0.95, "tp": 8, "fp": 0, "fn": 0},
        ]
        picked = select_fp_fn_exemplars(rows, top_fp=2, top_fn=2, max_total=4)
        self.assertEqual(2, picked["high_fp"][0]["sample_id"])
        self.assertEqual(3, picked["high_fn"][0]["sample_id"])
        self.assertIn("2", picked["sample_ids"])
        self.assertIn("3", picked["sample_ids"])

    def test_large_run_uses_fp_fn_exemplars(self):
        states = _fake_states(30, text_len=100)
        compact = compact_states_for_report(states)
        self.assertIn("examples_high_fp", compact)
        self.assertIn("examples_high_fn", compact)
        self.assertEqual("top_fp_and_top_fn", compact["exemplar_selection"]["strategy"])
        self.assertLessEqual(len(compact["examples_detail"]), REPORT_EXEMPLAR_MAX)

    def test_small_run_keeps_per_sample(self):
        states = _fake_states(3)
        compact = compact_states_for_report(states)
        self.assertEqual("table", compact.get("report_mode"))
        self.assertIn("1", compact)
        self.assertEqual(5000, len(compact["1"].get("text", "")))

    def test_storage_does_not_truncate_text_or_entities(self):
        state = _fake_states(1)["1"]
        slim = compact_sample_for_storage(state)
        self.assertEqual(state["text"], slim["text"])
        self.assertEqual(state["entities"], slim["entities"])
        self.assertNotIn("sentences", slim)

    def test_build_payload_json_size_bounded(self):
        states = _fake_states(100, text_len=500)
        payload = build_report_payload_states(states)
        blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        # 20 exemplars × ~500 chars text + entities; keep under ~2MB for report API
        self.assertLess(len(blob), 2_000_000)

    def test_summarize_micro_macro(self):
        states = _fake_states(2)
        summary = summarize_experiment_metrics(states)
        self.assertEqual(2, summary["sample_count"])
        self.assertIn("micro", summary)
        self.assertIn("macro", summary)

    def test_sample_archive_roundtrip(self):
        states = _fake_states(25, text_len=6000)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exp_id = "test-exp-archive"
            with patch("service.result.loader._get_path", return_value=root):
                write_states_bundle(exp_id, states)
                merged = load_states_for_report(exp_id, ResultLoader.load(exp_id))
                self.assertEqual(6000, len(merged["1"]["text"]))
                report = build_report_payload_states(exp_id=exp_id)
                self.assertEqual("charts", report.get("report_mode"))
                detail = report.get("examples_detail") or {}
                self.assertTrue(detail)
                any_full = next(iter(detail.values()))
                self.assertEqual(6000, len(any_full.get("text", "")))


if __name__ == "__main__":
    unittest.main()
