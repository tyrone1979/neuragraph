#!/usr/bin/env python3
"""CID dev.txt → 2-sample datasets; run NER + RE experiments; metrics + report."""
from __future__ import annotations

import json
import sys
import uuid
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.data_parser import CIDParser  # noqa: E402
from service.entity.test import TestLoader  # noqa: E402
from service.entity.runner import RunnerLoader  # noqa: E402
from service.meta.loader import MetaLoader  # noqa: E402
from langchain_core.runnables import RunnableConfig  # noqa: E402
from utils.conversion import jsonify_state  # noqa: E402

DEV_TXT = ROOT / "dev.txt"
DATASET_NAME = "cid_dev_2samples.csv"
NER_RUNNER = "wf_cid_ner_llm_eval"
RE_RUNNER = "wf_cid_re_llm_linear"
BASE = "http://127.0.0.1:5001"
def ner_row(art) -> dict[str, str]:
    mesh_to_text = {e.mesh: e.text for e in art.entities}
    rel_lines = []
    for head_mesh, tail_mesh in art.expected_relations:
        h = mesh_to_text.get(head_mesh, head_mesh)
        t = mesh_to_text.get(tail_mesh, tail_mesh)
        rel_lines.append(f"{h} | CID | {t}")
    return {
        "text": art.text,
        "labels": art.labels or "Chemical,Disease",
        "gold_entities": json.dumps(art.expected_entities, ensure_ascii=False),
        "gold_relations": "\n".join(rel_lines) if rel_lines else "",
    }


def re_row(art) -> dict[str, str]:
    entities = [
        {"text": e.text, "id": e.mesh, "label": e.etype}
        for e in art.entities
    ]
    rel_lines = [f"{head_mesh} | {tail_mesh}" for head_mesh, tail_mesh in art.expected_relations]
    return {
        "text": art.text,
        "entities": json.dumps(entities, ensure_ascii=False),
        "gold_relations": "\n".join(rel_lines) if rel_lines else "",
    }


def load_two_samples(dev_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    text = dev_path.read_text(encoding="utf-8")
    articles = CIDParser(text).get_articles()[:2]
    if len(articles) < 2:
        raise RuntimeError(f"Need at least 2 articles in {dev_path}, got {len(articles)}")
    return [ner_row(a) for a in articles], [re_row(a) for a in articles]


def save_datasets(ner_rows: list[dict[str, str]], re_rows: list[dict[str, str]]) -> None:
    TestLoader.save_csv_rows(
        NER_RUNNER,
        DATASET_NAME,
        ["text", "labels", "gold_entities", "gold_relations"],
        ner_rows,
    )
    TestLoader.save_csv_rows(
        RE_RUNNER,
        DATASET_NAME,
        ["text", "entities", "gold_relations"],
        re_rows,
    )
    print(f"  wrote tests/{NER_RUNNER}/{DATASET_NAME}")
    print(f"  wrote tests/{RE_RUNNER}/{DATASET_NAME}")


def run_experiment_local(runner_id: str, rows: list[dict]) -> tuple[str, dict]:
    exp_id = str(uuid.uuid4())
    exp_cfg = {
        "exp_id": exp_id,
        "name": f"CID {runner_id} (2 samples)",
        "runner_id": runner_id,
        "runner_type": "graph",
        "dataset": DATASET_NAME,
        "samples": len(rows),
        "status": "running",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "config": {"runner": runner_id, "dataset": DATASET_NAME},
    }
    MetaLoader.dump("exps", exp_id, exp_cfg)

    runner = RunnerLoader.load(runner_id)
    results: dict = {}
    for idx, row in enumerate(rows, start=1):
        params = jsonify_state(dict(row))
        config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
        if hasattr(runner, "compiled_graph"):
            state = runner.compiled_graph.invoke(params, config=config)
        else:
            state = runner.invoke(params) or {}
        if isinstance(state, dict):
            results[str(idx)] = state
        print(f"    sample {idx} done keys={list(state.keys()) if isinstance(state, dict) else '?'}")

    path = ROOT / "result" / exp_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "states.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    exp_cfg["status"] = "completed"
    exp_cfg["progress"] = 100
    MetaLoader.dump("exps", exp_id, exp_cfg)
    return exp_id, results


def fetch_report(exp_id: str, timeout: int = 180) -> str:
    url = f"{BASE}/stream/report/{exp_id}"
    buf = ""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace")
            if "[DONE]" in line:
                break
            if line.startswith("data: "):
                buf += line[6:].replace("\\n", "\n")
    return buf


def summarize_results(runner_id: str, results: dict) -> None:
    print(f"\n--- {runner_id} ---")
    for idx, state in sorted(results.items(), key=lambda x: int(x[0])):
        if not isinstance(state, dict):
            continue
        m = state.get("metrics") or {}
        ent = state.get("entities")
        rel = state.get("relations")
        print(f"  sample {idx}:")
        if m:
            print(f"    metrics: {json.dumps(m, ensure_ascii=False)[:200]}")
        if ent:
            print(f"    entities: {json.dumps(ent, ensure_ascii=False)[:180]}...")
        if rel:
            s = rel if isinstance(rel, str) else json.dumps(rel, ensure_ascii=False)
            print(f"    relations: {s[:180]}...")


def main() -> int:
    dev_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_TXT
    if not dev_path.is_file():
        print(f"Missing {dev_path}")
        return 1

    print(f"Parsing first 2 articles from {dev_path} ...")
    ner_rows, re_rows = load_two_samples(dev_path)
    for i, r in enumerate(re_rows, 1):
        print(f"  [{i}] text len={len(r['text'])}  entities={r['entities'][:80]}...")
        print(f"       gold_relations lines={len(r['gold_relations'].splitlines())}")

    print("\nSaving test datasets ...")
    save_datasets(ner_rows, re_rows)

    print(f"\n=== NER experiment ({NER_RUNNER}) ===")
    ner_exp, ner_res = run_experiment_local(NER_RUNNER, ner_rows)
    summarize_results(NER_RUNNER, ner_res)

    print(f"\n=== RE experiment ({RE_RUNNER}) ===")
    re_exp, re_res = run_experiment_local(RE_RUNNER, re_rows)
    summarize_results(RE_RUNNER, re_res)

    print("\n=== Reports (requires Flask on :5001) ===")
    for label, exp_id in [("NER", ner_exp), ("RE", re_exp)]:
        try:
            report = fetch_report(exp_id)
            out = ROOT / "tests" / f"cid_report_{label.lower()}.md"
            out.write_text(report, encoding="utf-8")
            print(f"  {label} report saved ({len(report)} chars) -> {out.relative_to(ROOT)}")
            print(f"  preview: {report[:300].replace(chr(10), ' ')}...")
        except Exception as ex:
            print(f"  {label} report skipped: {ex}")

    print(f"\nExperiment IDs:")
    print(f"  NER: /exp/{ner_exp}")
    print(f"  RE:  /exp/{re_exp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
