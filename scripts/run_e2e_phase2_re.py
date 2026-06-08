#!/usr/bin/env python3
"""
Phase 2: Read Flair NER entities → build RE CSV → run optimized CID RE on 500.

Input:  result/e2e_flair_ner/entities_500.json
Output: result/perf34_wf_e2e_flair_opt_re_summary.json (Table S18 row)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RE_RUNNER = "wf_cid_re_llm_linear_opt_20260604"
NER_ENTITIES = ROOT / "result" / "e2e_flair_ner" / "entities_500.json"
DATASET = "cdr_test_500_e2e.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
FIELDS = ["text", "entities", "gold_relations"]


def _bar(cur: int, total: int, w: int = 50) -> str:
    f = int(w * cur / total) if total else 0
    pct = int(100 * cur / total) if total else 0
    return f"\r  [{'#' * f}{'.' * (w - f)}] {cur}/{total} ({pct}%)"


def build_csv():
    from service.dataset_cid import load_source_articles
    from service.entity.test import TestLoader

    entities_all = json.loads(NER_ENTITIES.read_text(encoding="utf-8"))
    articles = load_source_articles(SOURCE)
    rows = []
    for idx, art in enumerate(articles, start=1):
        flair_entities = entities_all.get(str(idx), {})
        # Convert {Chemical: [...], Disease: [...]} to [{text, label, id}]
        ent_list = []
        for label, mentions in flair_entities.items():
            for text in (mentions if isinstance(mentions, list) else [str(mentions)]):
                if text and isinstance(text, str) and text.strip():
                    ent_list.append({"text": text.strip(), "label": str(label).strip(), "id": ""})
        # Build gold_relations from article (same as re_row)
        mesh_to_text = {e.mesh: e.text for e in art.entities}
        rel_lines = []
        for h_mesh, t_mesh in art.expected_relations:
            h = mesh_to_text.get(h_mesh, h_mesh)
            t = mesh_to_text.get(t_mesh, t_mesh)
            rel_lines.append(f"{h} | CID | {t}")
        rows.append({
            "text": art.text,
            "entities": json.dumps(ent_list, ensure_ascii=False),
            "gold_relations": "\n".join(rel_lines),
        })
    path = TestLoader.save_csv_rows(RE_RUNNER, DATASET, FIELDS, rows)
    print(f"Built {path} ({len(rows)} rows)")
    print(f"  Entity sets: {len(entities_all)}, avg entities/article: "
          f"{sum(len(json.loads(r['entities'])) for r in rows) / max(len(rows), 1):.1f}")


def run_re_batch():
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_sample_full, write_states_bundle
    from utils.workflow_metrics import compute_workflow_metrics

    exp = create_experiment_record(RE_RUNNER, DATASET, "graph",
                                   tuning_dataset=DATASET, test_dataset=DATASET)
    exp_id = exp["exp_id"]
    print(f"Running {RE_RUNNER} exp_id={exp_id} n=500")

    _, rows = TestLoader.load_by_id_file(RE_RUNNER, DATASET)
    total = len(rows)
    runner = RunnerLoader.load(RE_RUNNER)
    if not runner:
        raise RuntimeError(f"Runner not found: {RE_RUNNER}")

    states_path = ROOT / "result" / exp_id / "states.json"
    done = set()
    if states_path.is_file():
        try:
            prev = json.loads(states_path.read_text(encoding="utf-8"))
            done = {k for k, v in prev.items()
                    if k.isdigit() and isinstance(v, dict) and v.get("metrics")}
        except Exception:
            pass
    if done:
        print(f"  resume: {len(done)} already have metrics")

    store: dict[str, dict] = {}
    for idx, row in enumerate(rows, start=1):
        if str(idx) in done:
            continue
        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        payload = dict(row)
        (runner.compiled_graph if hasattr(runner, "compiled_graph") else runner).invoke(
            payload, config=config)
        state = runner.get_state(config)
        if state and state.values:
            values = dict(state.values)
            try:
                m = compute_workflow_metrics(RE_RUNNER, payload, values)
                if m:
                    values["metrics"] = m
            except Exception:
                pass
            store[str(idx)] = values
            write_sample_full(exp_id, idx, values)
        if idx % 10 == 0 or idx == total:
            write_states_bundle(exp_id, store)
        MetaLoader.update("exps", exp_id, {"progress": int(idx / total * 100),
                                           "status": "running" if idx < total else "completed"})
        print(_bar(idx, total), end="", flush=True)
    print()
    write_states_bundle(exp_id, store)

    from scripts._aggregate_exp_metrics import aggregate_states
    agg = aggregate_states(states_path)
    summary = {"runner_id": RE_RUNNER, "exp_id": exp_id, "dataset": DATASET, "n": total,
               "aggregate": agg}
    out = ROOT / "result" / "perf34_wf_e2e_flair_opt_re_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def print_metrics():
    from scripts._aggregate_exp_metrics import aggregate_states
    import glob
    # Find the latest summary
    summary_files = sorted(ROOT.glob("result/perf34_wf_e2e_flair_opt_re_summary.json"))
    if not summary_files:
        print("No summary found yet.")
        return
    agg = json.loads(summary_files[-1].read_text())["aggregate"]
    print(f"\nFlair NER → optimized RE (E2E, 500 articles):")
    print(f"  Micro: P={agg['micro'][0]:.3f}  R={agg['micro'][1]:.3f}  F1={agg['micro'][2]:.3f}")


def main():
    print("=" * 70)
    print("  E2E PHASE 2: Optimized CID RE on Flair NER entities")
    print("=" * 70)
    if not NER_ENTITIES.is_file():
        print("ERROR: Phase 1 entities not found. Run run_e2e_phase1_ner.py first.")
        return 1
    build_csv()
    run_re_batch()
    print_metrics()
    print("\n  Backup NER entities + RE states after completion!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
