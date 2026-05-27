#!/usr/bin/env python3
"""Clear tests/, create one sample CSV per workflow graph, run /stream/test for each."""
from __future__ import annotations

import csv
import json
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.graphutils import compute_graph_global_inputs  # noqa: E402

TESTS_DIR = ROOT / "tests"
GRAPHS_DIR = ROOT / "meta" / "graphs"
BASE = "http://127.0.0.1:5001"
LLM_TIMEOUT = 420
FAST_TIMEOUT = 90

# Known good inputs per workflow (overrides auto-fill).
WORKFLOW_INPUTS: dict[str, dict[str, str]] = {
    "wf_cid_ner_llm_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_cid_ner_flair_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_cid_re_llm_linear": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
        "gold_relations": "Aspirin|causes|headache",
    },
    "wf_cid_re_branch": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
        "gold_relations": "Aspirin|causes|headache",
    },
    "wf_doc_ner_llm_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical, Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_doc_ner_flair_eval": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    },
    "wf_doc_ner_loop_branch": {
        "text": "Aspirin treats pain. Metformin treats diabetes.",
        "labels": "Chemical,Disease",
        "expected_entities": json.dumps({"Chemical": ["Aspirin", "Metformin"]}),
    },
    "wf_doc_re_nested_branch": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_general_report_linear": {"text": "Aspirin is used to treat pain and inflammation."},
    "wf_kg_llm_full": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_kg_flair_full": {
        "text": "Aspirin may reduce the risk of heart disease.",
        "labels": "Chemical,Disease",
    },
    "wf_kg_syntax_loop": {
        "text": "Aspirin treats pain.",
        "doc_id": "sample1",
    },
    "wf_re_verify_llm_loop": {
        "text": "Aspirin may cause headache.",
        "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["headache"]}),
        "expected_relations": "Aspirin|causes|headache",
        "entity_link": json.dumps({"Aspirin": "Aspirin", "headache": "headache"}),
    },
    "wf_word_seg_llm_eval": {
        "text": "Biomedical text mining.",
        "expected": "Biomedical| |text| |mining| |.",
    },
}

FIELD_DEFAULTS: dict[str, str] = {
    "text": "Aspirin may reduce the risk of heart disease.",
    "sentence": "Aspirin treats pain.",
    "labels": "Chemical,Disease",
    "expected": "sample",
    "expected_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    "expected_relations": "Aspirin|treats|heart disease",
    "entity_link": json.dumps({"Aspirin": "Aspirin"}),
    "gold_entities": json.dumps({"Chemical": ["Aspirin"], "Disease": ["heart disease"]}),
    "gold_relations": "Aspirin | treats | heart disease",
    "doc_id": "sample1",
    "entities": "",
    "relations": "",
}


def list_workflow_ids() -> list[str]:
    return sorted(p.stem for p in GRAPHS_DIR.glob("wf_*.json"))


def clear_tests_dir() -> None:
    if TESTS_DIR.exists():
        shutil.rmtree(TESTS_DIR)
    TESTS_DIR.mkdir(parents=True)


def build_inputs(graph_id: str) -> dict[str, str]:
    if graph_id in WORKFLOW_INPUTS:
        return dict(WORKFLOW_INPUTS[graph_id])
    try:
        fields = compute_graph_global_inputs(graph_id)
    except Exception:
        fields = ["text"]
    if not fields:
        fields = ["text"]
    row: dict[str, str] = {}
    for f in fields:
        row[f] = FIELD_DEFAULTS.get(f, FIELD_DEFAULTS["text"])
    return row


def write_sample_csv(graph_id: str, row: dict[str, str]) -> Path:
    agent_dir = TESTS_DIR / graph_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "sample.csv"
    fieldnames = list(row.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    return path


def wait_stream_done(graph_id: str, params: dict[str, str], timeout: int) -> tuple[bool, str]:
    q = urllib.parse.urlencode({"graphId": graph_id, **params})
    url = f"{BASE}/stream/test?{q}"
    buf = ""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace")
                if "[DONE]" in line:
                    return True, buf[-300:] if buf else "DONE"
                if line.startswith("data: "):
                    buf += line[6:].replace("\\n", "\n")
                    if len(buf) > 800:
                        buf = buf[-800:]
    except Exception as ex:
        return False, str(ex)[:300]
    return False, (buf[-300:] if buf else "no [DONE]")


def main() -> int:
    wf_ids = list_workflow_ids()
    if not wf_ids:
        print("No workflow graphs found in meta/graphs/")
        return 1

    print(f"Clearing {TESTS_DIR} ...")
    clear_tests_dir()

    print(f"Generating 1 sample.csv per workflow ({len(wf_ids)} graphs) ...")
    inputs_by_id: dict[str, dict[str, str]] = {}
    for gid in wf_ids:
        row = build_inputs(gid)
        path = write_sample_csv(gid, row)
        inputs_by_id[gid] = row
        print(f"  {path.relative_to(ROOT)}  fields={list(row.keys())}")

    manifest = TESTS_DIR / "manifest.json"
    manifest.write_text(
        json.dumps({"workflows": inputs_by_id}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nRunning workflow tests via {BASE}/stream/test ...")
    results: list[dict] = []
    passed = failed = 0
    for gid in wf_ids:
        params = inputs_by_id[gid]
        timeout = LLM_TIMEOUT
        print(f"  [{gid}] timeout={timeout}s ...", flush=True)
        ok, detail = wait_stream_done(gid, params, timeout=timeout)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        results.append({"graph_id": gid, "status": status, "detail": detail[:300]})
        mark = "OK" if ok else "FAIL"
        print(f"    -> {mark}: {detail[:120]}")

    report_path = TESTS_DIR / "workflow_test_results.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": {"total": len(wf_ids), "passed": passed, "failed": failed},
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n=== Summary ===")
    print(f"Total: {len(wf_ids)}  Passed: {passed}  Failed: {failed}")
    print(f"Report: {report_path}")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  FAIL  {r['graph_id']}: {r['detail'][:100]}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
