"""Unit tests for nested loop regression fixtures."""
import unittest

from service.meta.loader import MetaLoader
from service.entity.graph import GraphLoader
from ui_tests.utils.nested_loop_graph_fixtures import (
    NESTED_LOOP_TEST_INPUT,
    build_nested_loop_graphs,
    verify_nested_loop_result,
)


class NestedLoopGraphFixturesTest(unittest.TestCase):
    def test_invoke_and_verify_three_level_nested_loop(self):
        graphs, ids = build_nested_loop_graphs("unit")
        try:
            for gid, meta in graphs.items():
                MetaLoader.dump("graphs", gid, meta)
            state = GraphLoader.load(ids["main"]).invoke(dict(NESTED_LOOP_TEST_INPUT))
            ok, detail = verify_nested_loop_result(state)
            self.assertTrue(ok, detail)
        finally:
            for gid in ids.values():
                if MetaLoader.exists("graphs", gid):
                    MetaLoader.delete("graphs", gid)


if __name__ == "__main__":
    unittest.main()
