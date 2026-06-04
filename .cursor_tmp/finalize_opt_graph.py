"""Revert Round 2 changes, create final optimized graph with Round 1 only."""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 1. Revert relation_result_to_id_pair to v0001 ──
idx_path = ROOT / "meta/agent_versions/relation_result_to_id_pair/index.json"
idx = json.loads(idx_path.read_text(encoding="utf-8"))
if idx.get("latest") == "v0002":
    idx["latest"] = "v0001"
    idx_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    # Restore agent to v0001 content
    v1 = json.loads(
        (ROOT / "meta/agent_versions/relation_result_to_id_pair/v0001.json").read_text(encoding="utf-8")
    )
    agent_path = ROOT / "meta/agents/relation_result_to_id_pair.json"
    if "content" in v1:
        v1["content"].pop("name", None)
        v1["content"].pop("version", None)
        agent_path.write_text(json.dumps(v1["content"], indent=2, ensure_ascii=False), encoding="utf-8")
    print("[1] Reverted relation_result_to_id_pair to v0001")
else:
    print(f"[1] relation_result_to_id_pair latest={idx.get('latest')} - no revert needed")

# ── 2. Create optimized graph ──
from service.experiment_optimize import _create_candidate_graph
RUNNER_ID = "wf_cid_re_llm_linear"
TUNING = "cid_dev_tuning_stratified_50.csv"
TEST = "cdr_test_500.csv"
versions = {"relation_verify_llm": "v0008"}
graph_id = f"{RUNNER_ID}_opt_20260604"

final = _create_candidate_graph(RUNNER_ID, versions, graph_id, datasets=[TUNING, TEST])
print(f"[2] Optimized graph: {final}")

# ── 3. Save summary ──
summary = {
    "optimized_graph_id": final,
    "accepted_versions": versions,
    "rounds": [
        {"round": 1, "target": "relation_verify_llm", "accepted": True,
         "f1_candidate": 0.6251, "delta": +0.0975,
         "change": "Prompt: reject endogenous substances + accept AE reporting language"},
        {"round": 2, "target": "relation_result_to_id_pair", "accepted": False,
         "f1_candidate": 0.622, "delta": -0.003,
         "change": "PGM guard widening — reverted (hurt F1)"},
    ]
}
sp = ROOT / "result" / "b47e0d53-aee9-4f3d-b7df-3ef18616a93a" / "optimize_rounds_summary.json"
sp.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[3] Summary: {sp}")
print(f"\nDone. Graph: {final}")
