#!/usr/bin/env python3
"""Build + run PubTator3 RE on BC5CDR test 500 for Table S18 comparison."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from service.dataset.parsers import load_articles_from_source, row_options_for_source
from service.dataset.rows import FORMAT_FIELDS, row_pubtator
from service.entity.test import TestLoader

PUBTATOR_FIELDS = FORMAT_FIELDS["pubtator"]


def load_source_articles(source):
    return load_articles_from_source(source)


def pubtator_row(art, source):
    return row_pubtator(art, rel_label=row_options_for_source(source)["rel_label"])

RUNNER = "wf_re_pubtator_dev10"
DATASET = "cdr_test_500.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"


def _progress_bar(cur: int, total: int, width: int = 50) -> str:
    filled = int(width * cur / total) if total else 0
    pct = int(100 * cur / total) if total else 0
    return f"\r  [{'#' * filled}{'.' * (width - filled)}] {cur}/{total} ({pct}%)"


def build_csv() -> None:
    articles = load_source_articles(SOURCE)
    rows = [pubtator_row(a, SOURCE) for a in articles]
    path = TestLoader.save_csv_rows(RUNNER, DATASET, PUBTATOR_FIELDS, rows)
    print(f"Built {path} ({len(rows)} rows)")


def run_batch() -> dict:
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_sample_full, write_states_bundle
    from utils.workflow_metrics import compute_workflow_metrics

    exp = create_experiment_record(RUNNER, DATASET, "graph",
                                   tuning_dataset=DATASET, test_dataset=DATASET)
    exp_id = exp["exp_id"]
    print(f"Running {RUNNER} exp_id={exp_id} n=500")

    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    total = len(rows)
    runner = RunnerLoader.load(RUNNER)
    if not runner:
        raise RuntimeError(f"Runner not found: {RUNNER}")

    exp_cfg = dict(exp)
    states_path = ROOT / "result" / exp_id / "states.json"
    done: set[str] = set()
    if states_path.is_file():
        try:
            prev = json.loads(states_path.read_text(encoding="utf-8"))
            done = {k for k, v in prev.items()
                    if k.isdigit() and isinstance(v, dict) and v.get("metrics")}
        except Exception:
            pass
    if done:
        print(f"  resume: {len(done)} samples ready")

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
                m = compute_workflow_metrics(RUNNER, payload, values)
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
        print(_progress_bar(idx, total), end="", flush=True)
    print()
    write_states_bundle(exp_id, store)

    # Aggregate
    from scripts._aggregate_exp_metrics import aggregate_states
    agg = aggregate_states(states_path)
    summary = {"runner_id": RUNNER, "exp_id": exp_id, "dataset": DATASET, "n": total,
               "aggregate": agg}
    out = ROOT / "result" / f"perf34_{RUNNER}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    build_csv()
    run_batch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
