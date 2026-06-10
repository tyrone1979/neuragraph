"""Unit tests for workflow family representative selection."""
import unittest

from utils.graphutils import (
    compute_states,
    parse_workflow_family,
    redundant_graph_ids,
    rebase_workflow_variant_from_baseline,
    select_representative_graph_ids,
)


class WorkflowFamilySelectionTest(unittest.TestCase):
    def test_opt_round_beats_parent_snapshot(self):
        fam = "wf_cid_re_llm_linear"
        parent = f"{fam}_opt_20260529_143039"
        r2 = f"{parent}_r2"
        picked = select_representative_graph_ids([parent, f"{parent}_r1", r2])
        self.assertEqual(picked, [r2])

    def test_baseline_kept_with_highest_opt_when_present(self):
        fam = "wf_cid_re_llm_linear"
        parent = f"{fam}_opt_20260529_143039"
        r2 = f"{parent}_r2"
        picked = select_representative_graph_ids([fam, parent, f"{parent}_r1", r2])
        self.assertEqual(picked, [fam, r2])

    def test_baseline_and_highest_opt_both_kept(self):
        ids = [
            "wf_cid_re_llm_linear",
            "wf_cid_re_llm_linear_opt_20260528_100124",
            "wf_cid_re_llm_linear_opt_20260529_143039_r2",
        ]
        self.assertEqual(
            select_representative_graph_ids(ids),
            [
                "wf_cid_re_llm_linear",
                "wf_cid_re_llm_linear_opt_20260529_143039_r2",
            ],
        )

    def test_subgraphs_are_own_family(self):
        ids = ["sg_cid_re_verify", "sg_relation_verify"]
        self.assertEqual(sorted(select_representative_graph_ids(ids)), sorted(ids))

    def test_redundant_is_complement_of_keep(self):
        ids = ["wf_a", "wf_a_opt_20260101", "wf_a_opt_20260101_r1"]
        keep = set(select_representative_graph_ids(ids))
        drop = set(redundant_graph_ids(ids))
        self.assertEqual(keep | drop, set(ids))
        self.assertFalse(keep & drop)

    def test_parent_opt_sort_key_before_rounds(self):
        parent = parse_workflow_family("wf_x_opt_20260529_143039")
        r2 = parse_workflow_family("wf_x_opt_20260529_143039_r2")
        self.assertLess(parent["sort_key"], r2["sort_key"])

    def test_opt_variant_inherits_baseline_topology(self):
        baseline = {
            "nodes": ["START", "e2e_entities_dedup_by_id", "cid_pair_generate", "END"],
            "edges": [["START", "e2e_entities_dedup_by_id"], ["e2e_entities_dedup_by_id", "cid_pair_generate"], ["cid_pair_generate", "END"]],
            "bindings": {"e2e_entities_dedup_by_id": {"entities": "{{ START.entities }}"}},
            "description": "baseline topology",
        }
        stale = {
            "nodes": ["START", "ontology_hypernym_filter", "cid_pair_generate", "END"],
            "edges": [["START", "ontology_hypernym_filter"], ["ontology_hypernym_filter", "cid_pair_generate"], ["cid_pair_generate", "END"]],
            "bindings": {"ontology_hypernym_filter": {"entities": "{{ START.entities }}"}},
            "description": "stale topology",
            "agentVersions": {"relation_verify_llm": "v0007"},
            "name": "CID RE Pipeline (linear) [optimized]",
            "created_at": "2026-05-29T14:52:48.202178",
        }
        graph_id = "wf_cid_re_llm_linear_opt_20260529_143039_r2"

        class _FakeMetaLoader:
            @staticmethod
            def load(kind, gid):
                if kind != "graphs":
                    return None
                if gid == "wf_cid_re_llm_linear":
                    return dict(baseline)
                if gid == graph_id:
                    return dict(stale)
                return None

        import utils.graphutils as graphutils

        original = graphutils.MetaLoader
        try:
            graphutils.MetaLoader = _FakeMetaLoader
            rebased = rebase_workflow_variant_from_baseline(graph_id, dict(stale))
        finally:
            graphutils.MetaLoader = original

        self.assertEqual(rebased["nodes"], baseline["nodes"])
        self.assertEqual(rebased["edges"], baseline["edges"])
        self.assertEqual(rebased["bindings"], baseline["bindings"])
        self.assertEqual(rebased["description"], baseline["description"])
        self.assertEqual(rebased["agentVersions"], {"relation_verify_llm": "v0007"})
        self.assertEqual(rebased["name"], stale["name"])
        self.assertEqual(rebased["created_at"], stale["created_at"])

    def test_compute_states_includes_nested_subgraph_inputs(self):
        fields = compute_states("wf_e2e_pubtator_re")
        self.assertIn("text", fields)
        self.assertIn("pmid", fields)
        self.assertIn("relations", fields)


if __name__ == "__main__":
    unittest.main()
