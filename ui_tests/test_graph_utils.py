"""Offline unit tests for graph JSON backup/normalize (no server)."""
import json
import unittest
from pathlib import Path

from ui_tests.graph_utils import (
    ALL_GRAPH_IDS,
    backup_graphs,
    graph_diff,
    load_graph_json,
    normalize_graph,
    restore_graph,
)


class GraphUtilsTest(unittest.TestCase):
    def test_all_graphs_have_backup(self):
        backup_graphs(force=True)
        for gid in ALL_GRAPH_IDS:
            self.assertTrue(
                (Path(__file__).resolve().parent.parent / "meta" / "graphs_backup" / f"{gid}.json").is_file(),
                f"missing backup for {gid}",
            )

    def test_normalize_ignores_created_at(self):
        a = {"name": "wf", "created_at": "2020-01-01", "nodes": ["START", "END"]}
        b = {"name": "wf", "created_at": "2026-05-25", "nodes": ["START", "END"]}
        self.assertEqual(normalize_graph(a), normalize_graph(b))

    def test_self_diff_empty(self):
        gid = ALL_GRAPH_IDS[0]
        data = load_graph_json(gid, from_backup=True)
        self.assertEqual(graph_diff(data, data), "")

    def test_restore_roundtrip(self):
        gid = ALL_GRAPH_IDS[0]
        original = load_graph_json(gid, from_backup=True)
        graphs_path = Path(__file__).resolve().parent.parent / "meta" / "graphs" / f"{gid}.json"
        graphs_path.write_text(
            json.dumps({**original, "name": "__mutated__"}, ensure_ascii=False),
            encoding="utf-8",
        )
        restore_graph(gid)
        restored = load_graph_json(gid, from_backup=False)
        self.assertEqual(graph_diff(original, restored), "")


if __name__ == "__main__":
    unittest.main()
