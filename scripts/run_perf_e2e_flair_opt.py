#!/usr/bin/env python3
"""§3.4 Task C: Flair NER → optimized CID RE on BC5CDR test 500. For Table S18 E2E row."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUNNER = "wf_e2e_flair_opt_re"
DATASET = "cdr_test_500.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
FIELDS = ["text", "labels", "gold_relations"]


def _bar(cur: int, total: int, w: int = 50) -> str:
    f = int(w * cur / total) if total else 0
    pct = int(100 * cur / total) if total else 0
    return f"\r  [{'#' * f}{'.' * (w - f)}] {cur}/{total} ({pct}%)"


def build_csv():
    from service.dataset_cid import load_source_articles, ner_row
    from service.entity.test import TestLoader
    articles = load_source_articles(SOURCE)
    rows = []
    for a in articles:
        nr = ner_row(a)
        rows.append({"text": nr["text"], "labels": nr["labels"],
                     "gold_relations": nr["gold_relations"]})
    path = TestLoader.save_csv_rows(RUNNER, DATASET, FIELDS, rows)
    print(f"Built {path} ({len(rows)} rows)")


def run_batch(*, limit: int | None = None, offset: int = 0, checkpoints: list[int] | None = None):
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_sample_full, write_states_bundle
    from utils.workflow_metrics import compute_workflow_metrics
    from scripts._aggregate_exp_metrics import aggregate_states

    exp = create_experiment_record(RUNNER, DATASET, "graph",
                                   tuning_dataset=DATASET, test_dataset=DATASET)
    exp_id = exp["exp_id"]
    print(f"Running {RUNNER} exp_id={exp_id} n=500")

    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    if offset:
        rows = rows[int(offset):]
    if limit is not None:
        rows = rows[: int(limit)]
    total = len(rows)
    base_idx = int(offset)
    print(f"Running {RUNNER} exp_id={exp_id} articles {base_idx + 1}-{base_idx + total}")

    runner = RunnerLoader.load(RUNNER)
    if not runner:
        raise RuntimeError(f"Runner not found: {RUNNER}")

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
        print(f"  resume: {len(done)} done")

    checkpoints = sorted(set(checkpoints or []))
    store: dict[str, dict] = {}
    if states_path.is_file():
        try:
            store = json.loads(states_path.read_text(encoding="utf-8"))
            if not isinstance(store, dict):
                store = {}
        except Exception:
            store = {}
    for i, row in enumerate(rows):
        idx = base_idx + i + 1
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
                m = compute_workflow_metrics(RUNNER, payload, values)
                if m:
                    values["metrics"] = m
            except Exception:
                pass
            store[str(idx)] = values
            write_sample_full(exp_id, idx, values)
        if idx in checkpoints:
            write_states_bundle(exp_id, store)
            agg = aggregate_states(states_path)
            print(f"\n--- checkpoint article {idx} ---")
            print(json.dumps({"exp_id": exp_id, "n": idx, "aggregate": agg}, indent=2))
        if (i + 1) % 10 == 0 or (i + 1) == total:
            write_states_bundle(exp_id, store)
        MetaLoader.update("exps", exp_id, {"progress": int((i + 1) / total * 100),
                                           "status": "running" if (i + 1) < total else "completed"})
        print(_bar(i + 1, total), end="", flush=True)
    print()
    write_states_bundle(exp_id, store)

    agg = aggregate_states(states_path)
    summary = {"runner_id": RUNNER, "exp_id": exp_id, "dataset": DATASET, "n": total,
               "aggregate": agg}
    out = ROOT / "result" / f"perf34_{RUNNER}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run wf_e2e_flair_opt_re on cdr_test_500")
    parser.add_argument("--limit", type=int, default=0, help="Debug: max articles (0 = all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N articles (0-based)")
    parser.add_argument("--skip-build", action="store_true", help="Use existing CSV")
    parser.add_argument("--checkpoint", type=int, action="append", default=[],
                        help="Print aggregate metrics after these sample indices (repeatable)")
    args = parser.parse_args()
    if not args.skip_build:
        build_csv()
    limit = args.limit if args.limit > 0 else None
    run_batch(limit=limit, offset=args.offset, checkpoints=args.checkpoint or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
