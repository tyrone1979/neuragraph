#!/usr/bin/env python3
"""
Phase 1: Run Flair NER on 500 CDR test articles. Persist entities to disk.
Output: result/e2e_flair_ner/entities_500.json  (label→mentions dict per article)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUNNER = "wf_doc_ner_flair_sent_eval"
DATASET = "cdr_test_500.csv"
SOURCE = ROOT / "comparison" / "data" / "CDR" / "test.txt"
OUT_DIR = ROOT / "result" / "e2e_flair_ner"
FIELDS = ["text", "labels", "gold_entities", "gold_relations"]


def _bar(cur: int, total: int, w: int = 50) -> str:
    f = int(w * cur / total) if total else 0
    pct = int(100 * cur / total) if total else 0
    return f"\r  [{'#' * f}{'.' * (w - f)}] {cur}/{total} ({pct}%)"


def build_csv():
    from service.dataset_cid import NER_FIELDS, load_source_articles, ner_row
    from service.entity.test import TestLoader
    articles = load_source_articles(SOURCE)
    rows = [ner_row(a) for a in articles]
    path = TestLoader.save_csv_rows(RUNNER, DATASET, NER_FIELDS, rows)
    print(f"Built {path} ({len(rows)} rows)")


def run_ner_batch():
    from langchain_core.runnables import RunnableConfig
    from service.chat.commands import create_experiment_record
    from service.entity.runner import RunnerLoader
    from service.entity.test import TestLoader
    from service.meta.loader import MetaLoader
    from service.result.loader import write_states_bundle

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entities_file = OUT_DIR / "entities_500.json"

    # Resume check
    done_samples: dict[str, dict] = {}
    if entities_file.is_file():
        done_samples = json.loads(entities_file.read_text(encoding="utf-8"))
    print(f"  Existing entities: {len(done_samples)} articles")

    exp = create_experiment_record(RUNNER, DATASET, "graph")
    exp_id = exp["exp_id"]
    print(f"Running Flair NER exp_id={exp_id} n=500")

    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    total = len(rows)
    runner = RunnerLoader.load(RUNNER)
    if not runner:
        raise RuntimeError(f"Runner not found: {RUNNER}")

    exp_cfg = dict(exp)
    store: dict[str, dict] = {}
    for idx, row in enumerate(rows, start=1):
        sid = str(idx)
        if sid in done_samples:
            continue

        sample = dict(row)
        if sample.get("gold_entities") and not sample.get("expected_entities"):
            sample["expected_entities"] = sample["gold_entities"]

        config = RunnableConfig(configurable={"thread_id": f"{exp_id}_{idx}"})
        (runner.compiled_graph if hasattr(runner, "compiled_graph") else runner).invoke(
            sample, config=config)

        state = runner.get_state(config)
        if state and state.values:
            values = dict(state.values)
            entities = values.get("entities")
            if isinstance(entities, dict):
                done_samples[sid] = dict(entities)
            store[sid] = values

        # Persist every 10
        if idx % 10 == 0 or idx == total:
            entities_file.write_text(json.dumps(
                done_samples, ensure_ascii=False, indent=2), encoding="utf-8")
            write_states_bundle(exp_id, store)
            print(f"  Flushed {len(done_samples)} entity sets", flush=True)

        MetaLoader.update("exps", exp_id, {"progress": int(idx / total * 100),
                                           "status": "running" if idx < total else "completed"})
        print(_bar(idx, total), end="", flush=True)
    print()
    # Final flush
    entities_file.write_text(json.dumps(
        done_samples, ensure_ascii=False, indent=2), encoding="utf-8")
    write_states_bundle(exp_id, store)
    print(f"NER done. {len(done_samples)} entity sets saved to {entities_file}")
    # Backup
    import shutil
    shutil.copy2(entities_file, OUT_DIR / "entities_500.json.BACKUP")
    return str(entities_file)


def main():
    print("=" * 70)
    print("  E2E PHASE 1: Flair NER (500 articles)")
    print("=" * 70)
    build_csv()
    run_ner_batch()
    print("\nPhase 1 complete. Run phase_2_re.py next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
