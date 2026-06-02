"""Tests for bulk LLM link updates on LLM agents."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service.llm_link_bulk import bulk_update_llm_links


class LlmLinkBulkTests(unittest.TestCase):
    def test_dry_run_updates_all_llm_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_dir = root / "agents"
            llms_dir = root / "llms"
            agents_dir.mkdir()
            llms_dir.mkdir()

            (llms_dir / "deepseek.json").write_text(
                json.dumps({"name": "DeepSeek", "type": "openai", "model": "deepseek-chat"}),
                encoding="utf-8",
            )
            (agents_dir / "ner_llm.json").write_text(
                json.dumps({"name": "NER", "type": "LLM", "model": "kimi-2.6", "inputs": ["text"]}),
                encoding="utf-8",
            )
            (agents_dir / "eval_metrics.json").write_text(
                json.dumps({"name": "Metrics", "type": "PGM", "inputs": ["predicted"]}),
                encoding="utf-8",
            )

            def fake_get_path(name: str) -> Path:
                path = root / name
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch("service.meta.loader._get_path", fake_get_path):
                result = bulk_update_llm_links("deepseek", dry_run=True)

            self.assertEqual(result.get("updated_count"), 1)
            self.assertEqual(result["updated"][0]["agent_id"], "ner_llm")
            self.assertEqual(result["updated"][0]["old_model"], "kimi-2.6")
            self.assertEqual(result["updated"][0]["new_model"], "deepseek")
            self.assertIn("kimi-2.6", (agents_dir / "ner_llm.json").read_text(encoding="utf-8"))

    def test_source_model_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_dir = root / "agents"
            llms_dir = root / "llms"
            agents_dir.mkdir()
            llms_dir.mkdir()

            (llms_dir / "deepseek.json").write_text(json.dumps({"model": "x"}), encoding="utf-8")
            (agents_dir / "a1.json").write_text(
                json.dumps({"name": "A1", "type": "LLM", "model": "kimi-2.6"}),
                encoding="utf-8",
            )
            (agents_dir / "a2.json").write_text(
                json.dumps({"name": "A2", "type": "LLM", "model": "gpt-oss_120b"}),
                encoding="utf-8",
            )

            def fake_get_path(name: str) -> Path:
                path = root / name
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch("service.meta.loader._get_path", fake_get_path):
                result = bulk_update_llm_links(
                    "deepseek", source_model="kimi-2.6", dry_run=True
                )

            self.assertEqual(result.get("updated_count"), 1)
            self.assertEqual(result["updated"][0]["agent_id"], "a1")


if __name__ == "__main__":
    unittest.main()
