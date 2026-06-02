"""Unit tests for workflow family representative selection."""
import unittest

from utils.graphutils import parse_workflow_family, redundant_graph_ids, select_representative_graph_ids


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


if __name__ == "__main__":
    unittest.main()
