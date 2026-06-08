#!/usr/bin/env python3
"""§3.4 Task B: build cdr_test_500.csv and batch-run CID RE on BC5CDR test (500, oracle entities)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.dataset_cid import RE_FIELDS, load_source_articles, re_row
from service.entity.test import TEST_DIR, TestLoader
from service.meta.loader import MetaLoader

DATASET = "cdr_test_500.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
DEV_SOURCE = ROOT / "data" / "raw" / "dev.txt"
DEV50_DATASET = "cid_dev_tuning_stratified_50.csv"
RUNNER_BASELINE = "wf_cid_re_llm_linear"


def _persist_sample(
    exp_cfg: dict, runner, runner_id: str, idx: int, rows: list
) -> None:
    from langchain_core.runnables import RunnableConfig
    from utils.workflow_metrics import compute_workflow_metrics

    exp_id = exp_cfg["exp_id"]
    path = ROOT / "result" / exp_id
    path.mkdir(parents=True, exist_ok=True)
    states_file = path / "states.json"
    result: dict[str, Any] = {}
    if states_file.is_file():
        result = json.loads(states_file.read_text(encoding="utf-8"))

    config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
    state = runner.get_state(config)
    if state and state.values:
        values = dict(state.values)
        row = rows[idx - 1] if idx - 1 < len(rows) else {}
        try:
            metrics = compute_workflow_metrics(runner_id, row, values)
        except Exception as exc:
            metrics = {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "rel_tp": 0,
                "rel_fp": 0,
                "rel_fn": 0,
                "_metrics_error": str(exc)[:300],
            }
        if metrics:
            values["metrics"] = metrics
        result[str(idx)] = values

    from service.result.loader import write_states_bundle

    write_states_bundle(exp_id, result, touch_sample_ids={str(idx)})


def _load_script_module(name: str, filename: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _aggregate(states_path: Path) -> dict:
    return _load_script_module("agg", "_aggregate_exp_metrics.py").aggregate_states(
        states_path
    )


def _s17_metrics(states_path: Path) -> dict:
    return _load_script_module("s17", "s17_metrics_compare.py").metrics_from_states(
        states_path
    )


def _s17_format(cur: dict, *, milestone: int, total: int) -> str:
    return _load_script_module("s17", "s17_metrics_compare.py").format_s17_report(
        cur, milestone=milestone, total=total
    )


def _s17_checkpoint(states_path: Path, milestone: int, *, total: int) -> None:
    _load_script_module("s17", "s17_metrics_compare.py").print_checkpoint(
        states_path, milestone, total=total
    )


def build_csv(
    runner_id: str,
    *,
    dataset: str = DATASET,
    source: Path | None = None,
    dev_stratified_50: bool = False,
) -> Path | None:
    if dataset != DATASET and (TEST_DIR / runner_id / dataset).is_file():
        print(f"Using existing {dataset} for {runner_id}")
        return TEST_DIR / runner_id / dataset
    src = source or (DEV_SOURCE if dev_stratified_50 else SOURCE)
    articles = load_source_articles(src)
    if dev_stratified_50:
        from service.dataset_cid import stratified_pick

        picked, _ = stratified_pick(articles, 50)
        rows = [re_row(a) for a in picked]
        out_name = dataset
    else:
        rows = [re_row(a) for a in articles]
        out_name = dataset
    path = TestLoader.save_csv_rows(runner_id, out_name, RE_FIELDS, rows)
    print(f"Wrote {path} ({len(rows)} rows) from {src.name}")
    return path


def _progress_bar(current: int, total: int, *, width: int = 50) -> str:
    """Compact single-line progress bar (no IDE cache bloat)."""
    filled = int(width * current / total) if total else 0
    bar = "#" * filled + "." * (width - filled)
    pct = int(100 * current / total) if total else 0
    return f"\r  [{bar}] {current}/{total} ({pct}%)"


def run_batch(
    runner_id: str,
    *,
    dataset: str = DATASET,
    limit: int | None = None,
    exp_id: str | None = None,
) -> dict:
    from langchain_core.runnables import RunnableConfig

    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader

    if exp_id:
        exp = MetaLoader.load("exps", exp_id) or {}
        if not exp:
            raise RuntimeError(f"experiment not found: {exp_id}")
    else:
        exp = create_experiment_record(
            runner_id, dataset, "graph", tuning_dataset=dataset, test_dataset=dataset
        )
        exp_id = exp["exp_id"]
    if not exp_id:
        exp_id = exp["exp_id"]

    _, rows = TestLoader.load_by_id_file(runner_id, dataset)
    if limit is not None:
        rows = rows[: int(limit)]
        MetaLoader.update("exps", exp_id, {"samples": len(rows)})

    runner = RunnerLoader.load(runner_id)
    if runner is None:
        raise RuntimeError(f"runner not found: {runner_id}")

    exp_cfg = dict(exp)
    total = len(rows)
    states_path = ROOT / "result" / exp_id / "states.json"
    done: set[str] = set()
    if states_path.is_file():
        try:
            prev = json.loads(states_path.read_text(encoding="utf-8"))
            done = {
                k
                for k, v in prev.items()
                if str(k).isdigit() and isinstance(v, dict) and v.get("metrics")
            }
        except Exception:
            pass
    if done:
        print(f"  resume: {len(done)} samples already with metrics")
    print(f"Running {runner_id} exp_id={exp_id} n={total}")

    for idx, row in enumerate(rows, start=1):
        if str(idx) in done:
            continue
        sample = dict(row)
        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        if hasattr(runner, "compiled_graph"):
            runner.compiled_graph.invoke(sample, config=config)
        else:
            runner.invoke(sample, config=config)
        _persist_sample(exp_cfg, runner, runner_id, idx, rows)
        status = "running" if idx < total else "completed"
        MetaLoader.update(
            "exps",
            exp_id,
            {
                "progress": int(idx / total * 100) if total else 100,
                "status": status,
            },
        )
        print(_progress_bar(idx, total), end="", flush=True)
        if idx % 100 == 0 and states_path.is_file():
            _s17_checkpoint(states_path, idx, total=total)
    print()  # final newline after progress bar

    if states_path.is_file():
        cur = _s17_metrics(states_path)
        print(_s17_format(cur, milestone=total, total=total), flush=True)

    agg = _aggregate(states_path)
    summary = {
        "runner_id": runner_id,
        "exp_id": exp_id,
        "dataset": dataset,
        "n": total,
        "aggregate": agg,
    }
    out = ROOT / "result" / f"perf34_{runner_id}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="§3.4 RE test-500 batch (oracle entities)")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument(
        "--runner",
        default=RUNNER_BASELINE,
        help=f"Workflow id (default: {RUNNER_BASELINE})",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--exp-id", default="", help="Resume existing experiment")
    parser.add_argument("--dataset", default=DATASET, help="CSV under tests/<runner>/")
    parser.add_argument(
        "--dev50",
        action="store_true",
        help="Use cid_dev_tuning_stratified_50.csv from data/raw/dev.txt",
    )
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear existing states for --exp-id before run",
    )
    args = parser.parse_args()

    runner_id = (args.runner or RUNNER_BASELINE).strip()
    dataset = DEV50_DATASET if args.dev50 else (args.dataset or DATASET).strip()
    if not args.skip_build:
        build_csv(
            runner_id,
            dataset=dataset,
            dev_stratified_50=args.dev50 or dataset == DEV50_DATASET,
        )
    elif args.build_only:
        build_csv(
            runner_id,
            dataset=dataset,
            dev_stratified_50=args.dev50 or dataset == DEV50_DATASET,
        )
        return 0
    if args.build_only:
        return 0

    limit = args.limit if args.limit > 0 else None
    resume_id = args.exp_id.strip() or None
    if resume_id and args.fresh:
        import shutil

        result_dir = ROOT / "result" / resume_id
        if result_dir.is_dir():
            shutil.rmtree(result_dir)
            print(f"Cleared result/{resume_id}")
        MetaLoader.update(
            "exps",
            resume_id,
            {
                "dataset": dataset,
                "tuning_dataset": dataset,
                "test_dataset": dataset,
                "samples": 50 if dataset == DEV50_DATASET else 500,
                "progress": 0,
                "status": "pending",
            },
        )
    run_batch(runner_id, dataset=dataset, limit=limit, exp_id=resume_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
