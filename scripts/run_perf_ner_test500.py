#!/usr/bin/env python3
"""§3.4 Task A: build cdr_test_500.csv and batch-run NER on BC5CDR test (500 articles)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.dataset_cid import NER_FIELDS, load_source_articles, ner_row
from service.entity.test import TestLoader

DATASET = "cdr_test_500.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
RUNNERS = (
    "wf_doc_ner_flair_sent_eval",
    "wf_doc_ner_llm_eval",
)


def _progress_bar(current: int, total: int, *, width: int = 50) -> str:
    filled = int(width * current / total) if total else 0
    bar = "#" * filled + "." * (width - filled)
    pct = int(100 * current / total) if total else 0
    return f"\r  [{bar}] {current}/{total} ({pct}%)"


def _coerce_ner_doc(obj: Any) -> dict | None:
    """Normalize gold/predicted entities to {label: [str, ...]} for MetricsCalculation."""
    from ast import literal_eval

    if obj is None:
        return None
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            if isinstance(v, list):
                out[str(k)] = [str(x) for x in v if x is not None]
            elif v is not None:
                out[str(k)] = [str(v)]
        return out or None
    if not isinstance(obj, str):
        return None
    s = obj.strip()
    if not s or s.startswith("{") is False and s.startswith("[") is False:
        return None
    for parser in (json.loads, literal_eval):
        try:
            parsed = parser(s)
            return _coerce_ner_doc(parsed)
        except Exception:
            continue
    return None


def _safe_ner_metrics(calc: Any, expected: Any, predicted: Any) -> dict | None:
    gold = _coerce_ner_doc(expected)
    pred = _coerce_ner_doc(predicted)
    if not gold or not pred:
        return None
    try:
        return calc.calculate(gold, pred)
    except Exception as exc:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "_metrics_error": str(exc)[:300],
        }


def _persist_sample(exp_cfg: dict, runner, idx: int, rows: list) -> None:
    """Write states.json per sample; keep eval_metrics output, skip broken graph recompute."""
    from langchain_core.runnables import RunnableConfig

    exp_id = exp_cfg["exp_id"]
    path = ROOT / "result" / exp_id
    path.mkdir(parents=True, exist_ok=True)
    states_file = path / "states.json"
    result = {}
    if states_file.is_file():
        result = json.loads(states_file.read_text(encoding="utf-8"))

    config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
    state = runner.get_state(config)
    if state and state.values:
        values = dict(state.values)
        row = rows[idx - 1] if idx - 1 < len(rows) else {}
        expected = (
            row.get("expected_entities")
            or row.get("gold_entities")
            or row.get("expected")
        )
        predicted = values.get("entities") or values.get("predicted")
        if expected and predicted and not values.get("metrics"):
            calc = __import__(
                "plugin.plugin_loader", fromlist=["get_plugin"]
            ).get_plugin("MetricsCalculation")
            if calc:
                metrics = _safe_ner_metrics(calc, expected, predicted)
                if metrics:
                    values["metrics"] = metrics
        result[str(idx)] = values

    from service.result.loader import write_states_bundle

    write_states_bundle(exp_id, result, touch_sample_ids={str(idx)})


def _aggregate_ner(states_path: Path) -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "agg", ROOT / "scripts" / "_aggregate_exp_metrics.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.aggregate_states(states_path)


def build_csvs() -> None:
    articles = load_source_articles(SOURCE)
    rows = [ner_row(a) for a in articles]
    for runner_id in RUNNERS:
        path = TestLoader.save_csv_rows(runner_id, DATASET, NER_FIELDS, rows)
        print(f"Wrote {path} ({len(rows)} rows) for {runner_id}")


def run_batch(
    runner_id: str, *, limit: int | None = None, exp_id: str | None = None
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
        exp = create_experiment_record(runner_id, DATASET, "graph")
        exp_id = exp["exp_id"]
    if not exp_id:
        exp_id = exp["exp_id"]
    _, rows = TestLoader.load_by_id_file(runner_id, DATASET)
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
        print(f"  resume: {len(done)} samples already have metrics")
    print(f"Running {runner_id} exp_id={exp_id} n={total}")

    for idx, row in enumerate(rows, start=1):
        if str(idx) in done:
            continue
        sample = dict(row)
        if sample.get("gold_entities") and not sample.get("expected_entities"):
            sample["expected_entities"] = sample["gold_entities"]
        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        if hasattr(runner, "compiled_graph"):
            runner.compiled_graph.invoke(sample, config=config)
        else:
            runner.invoke(sample, config=config)
        _persist_sample(exp_cfg, runner, idx, rows)
        status = "running" if idx < total else "completed"
        MetaLoader.update(
            "exps",
            exp_id,
            {"progress": int(idx / total * 100) if total else 100, "status": status},
        )
        print(_progress_bar(idx, total), end="", flush=True)
    print()

    agg = _aggregate_ner(states_path)
    summary = {
        "runner_id": runner_id,
        "exp_id": exp_id,
        "dataset": DATASET,
        "n": total,
        "aggregate": agg,
    }
    out = ROOT / "result" / f"perf34_{runner_id}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="§3.4 NER test-500 batch")
    parser.add_argument("--build-only", action="store_true", help="Only write CSVs")
    parser.add_argument(
        "--runner",
        choices=RUNNERS,
        default="",
        help="Run one runner (default: both)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Debug: max articles")
    parser.add_argument(
        "--exp-id",
        default="",
        help="Resume an existing experiment (skip samples that already have metrics)",
    )
    args = parser.parse_args()

    build_csvs()
    if args.build_only:
        return 0

    limit = args.limit if args.limit > 0 else None
    resume_id = args.exp_id.strip() or None
    targets = [args.runner] if args.runner else list(RUNNERS)
    for rid in targets:
        run_batch(rid, limit=limit, exp_id=resume_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
