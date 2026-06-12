"""Offline unit tests for graph JSON backup/normalize (no server)."""
import json
import unittest
from pathlib import Path

from ui_tests.utils.graph_workflow_json_utils import (
    BACKUP,
    GRAPHS,
    backup_graphs,
    discover_graph_ids,
    graph_diff,
    graph_run_params,
    load_graph_json,
    normalize_graph,
    restore_graph,
)


class GraphWorkflowJsonUtilsTest(unittest.TestCase):
    def test_all_live_graphs_have_backup(self):
        backup_graphs(force=True)
        live = discover_graph_ids(from_backup=False)
        self.assertGreater(len(live), 0)
        for gid in live:
            self.assertTrue(
                (BACKUP / f"{gid}.json").is_file(),
                f"missing backup for {gid}",
            )

    def test_graph_run_params_uses_csv_when_present(self):
        params = graph_run_params("wf_cid_re_llm_linear")
        self.assertIn("text", params)

    def test_normalize_ignores_created_at(self):
        a = {"name": "wf", "created_at": "2020-01-01", "nodes": ["START", "END"]}
        b = {"name": "wf", "created_at": "2026-05-25", "nodes": ["START", "END"]}
        self.assertEqual(normalize_graph(a), normalize_graph(b))

    def test_empty_agent_versions_and_flow_nodes_equivalent(self):
        base = {
            "nodes": ["START", "syntax_dep_parse", "END"],
            "edges": [["START", "syntax_dep_parse"], ["syntax_dep_parse", "END"]],
        }
        with_extra = {**base, "agentVersions": {}, "flowNodes": {}}
        self.assertEqual(graph_diff(base, with_extra), "")

    def test_visual_data_ignored_in_diff(self):
        base = {
            "nodes": ["START", "ner_llm", "END"],
            "edges": [["START", "ner_llm"], ["ner_llm", "END"]],
        }
        with_layout = {
            **base,
            "visualData": {"layout": {"START": {"x": 1, "y": 2}, "ner_llm": {"x": 3, "y": 4}}},
        }
        self.assertEqual(graph_diff(base, with_layout), "")

    def test_subgraph_expansion_matches_flattened_editor(self):
        backup = {
            "nodes": ["START", "sg_e2e_pubtator_re", "eval_metrics_relation", "END"],
            "edges": [
                ["START", "sg_e2e_pubtator_re"],
                ["sg_e2e_pubtator_re", "eval_metrics_relation"],
                ["eval_metrics_relation", "END"],
            ],
            "bindings": {
                "eval_metrics_relation": {
                    "relations": "{{ relations }}",
                    "ground_truth": "{{ START.gold_relations }}",
                    "entities": "{{ START.entities }}",
                },
            },
        }
        flattened = {
            "nodes": ["START", "relation_extract_pubtator", "eval_metrics_relation", "END"],
            "edges": [
                ["START", "relation_extract_pubtator"],
                ["relation_extract_pubtator", "eval_metrics_relation"],
                ["eval_metrics_relation", "END"],
            ],
            "bindings": {
                "relation_extract_pubtator": {"text": "{{ text }}", "pmid": "{{ pmid }}"},
                "eval_metrics_relation": {
                    "relations": "{{ relations }}",
                    "ground_truth": "{{ START.gold_relations }}",
                    "entities": "{{ START.entities }}",
                },
            },
        }
        self.assertEqual(graph_diff(backup, flattened), "")

    def test_self_diff_empty(self):
        ids = discover_graph_ids(from_backup=True)
        self.assertTrue(ids)
        gid = ids[0]
        data = load_graph_json(gid, from_backup=True)
        self.assertEqual(graph_diff(data, data), "")

    def test_restore_roundtrip(self):
        ids = discover_graph_ids(from_backup=False)
        self.assertTrue(ids)
        gid = ids[0]
        original = load_graph_json(gid, from_backup=True)
        graphs_path = GRAPHS / f"{gid}.json"
        graphs_path.write_text(
            json.dumps({**original, "name": "__mutated__"}, ensure_ascii=False),
            encoding="utf-8",
        )
        restore_graph(gid)
        restored = load_graph_json(gid, from_backup=False)
        self.assertEqual(graph_diff(original, restored), "")


if __name__ == "__main__":
    unittest.main()
