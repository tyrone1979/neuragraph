"""Finalize optimized graph from accepted Round 1 (relation_verify_llm v0008)."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from service.meta.loader import MetaLoader
from service.experiment_optimize import _create_candidate_graph

RUNNER_ID = "wf_cid_re_llm_linear"
TUNING_CSV = "cid_dev_tuning_stratified_50.csv"
TEST_CSV = "cdr_test_500.csv"

# Round 1 accepted: relation_verify_llm was bumped to v0008
versions = {"relation_verify_llm": "v0008"}
graph_id = f"{RUNNER_ID}_opt_20260604"

final = _create_candidate_graph(RUNNER_ID, versions, graph_id, datasets=[TUNING_CSV, TEST_CSV])
print(f"Optimized graph: {final}")
print(f"Pinned versions: {json.dumps(versions)}")

summary = {
    "optimized_graph_id": final,
    "accepted_versions": versions,
    "round_results": [
        {"round": 1, "target": "relation_verify_llm", "accepted": True,
         "f1_candidate": 0.6251, "delta_f1": +0.0975,
         "note": "Prompt: reject endogenous substances + accept AE reporting language"},
        {"round": 2, "target": "relation_result_to_id_pair", "accepted": False,
         "f1_candidate": 0.622, "delta_f1": -0.003,
         "note": "PGM guard widening hurt F1, reverted"},
    ]
}
Path(ROOT / "result" / "b47e0d53-aee9-4f3d-b7df-3ef18616a93a" / "optimize_rounds_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8",
)
print("\nSummary saved.")
print(f"\nNext: 'Run optimized test on 500' with graph: {final}")
