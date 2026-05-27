#!/usr/bin/env python3
"""Profile wf_cid_re_llm_linear: per-node timing + pair counts."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.runnables import RunnableConfig  # noqa: E402
from service.entity.runner import RunnerLoader  # noqa: E402
from service.entity.test import TestLoader  # noqa: E402
from utils.conversion import jsonify_state  # noqa: E402
from plugin.plugin_loader import get_plugin  # noqa: E402

RUNNER = "wf_cid_re_llm_linear"
DATASET = "cid_dev_2samples.csv"
NODES = (
    "ner_llm",
    "ontology_synonym_resolve",
    "ontology_hypernym_filter",
    "relation_extract_llm",
)


def pair_count(entities) -> int:
    if isinstance(entities, str):
        try:
            entities = json.loads(entities)
        except json.JSONDecodeError:
            return 0
    if not isinstance(entities, dict):
        return 0
    chems = entities.get("Chemical") or []
    dis = entities.get("Disease") or []
    return len(chems) * len(dis)


def main() -> int:
    sample_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    _, rows = TestLoader.load_by_id_file(RUNNER, DATASET)
    if sample_idx < 1 or sample_idx > len(rows):
        print(f"sample_idx must be 1..{len(rows)}")
        return 1

    row = jsonify_state(dict(rows[sample_idx - 1]))
    runner = RunnerLoader.load(RUNNER)
    config: RunnableConfig = {"configurable": {"thread_id": f"profile_{int(time.time())}"}}

    print(f"=== Profile {RUNNER} sample {sample_idx} ===")
    print(f"text len={len(row.get('text', ''))}")
    gold = row.get("gold_relations", "")
    print(f"gold relations: {len(str(gold).splitlines())} lines")

    t0 = time.perf_counter()
    last = t0
    node_times: dict[str, float] = {}
    node_outputs: dict[str, dict] = {}

    for chunk in runner.stream(row, config=config, stream_mode="updates", subgraphs=True):
        now = time.perf_counter()
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue
        _path, payload = chunk
        if not isinstance(payload, dict):
            continue
        for node, update in payload.items():
            if node not in NODES:
                continue
            elapsed = now - last
            node_times[node] = node_times.get(node, 0.0) + elapsed
            last = now
            if isinstance(update, dict):
                node_outputs[node] = update
            print(f"  [{node:32s}] +{elapsed:6.1f}s  keys={list(update.keys()) if isinstance(update, dict) else '?'}")

    total = time.perf_counter() - t0
    print(f"\n--- Node timings (stream gaps) ---")
    for node in NODES:
        print(f"  {node:32s} {node_times.get(node, 0.0):6.1f}s")
    print(f"  {'TOTAL':32s} {total:6.1f}s")

    ner_ent = node_outputs.get("ner_llm", {}).get("entities")
    filt_ent = node_outputs.get("ontology_hypernym_filter", {}).get("filtered_entities")
    rels = node_outputs.get("relation_extract_llm", {}).get("relations")
    print(f"\n--- Outputs ---")
    print(f"  NER entities: {json.dumps(ner_ent, ensure_ascii=False)[:200]}...")
    print(f"  NER pairs: {pair_count(ner_ent)}")
    print(f"  Filtered pairs: {pair_count(filt_ent)}")
    print(f"  Relations: {rels}")

    if row.get("gold_relations") and rels is not None:
        calc = get_plugin("MetricsCalculation")
        exp = calc.parse_relation_pairs(row["gold_relations"])
        pred = calc.parse_relation_pairs(rels)
        m = calc.calculate(exp, pred)
        print(f"  RE metrics: P={m.get('precision',0):.3f} R={m.get('recall',0):.3f} F1={m.get('f1',0):.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
