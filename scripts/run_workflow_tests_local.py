#!/usr/bin/env python3
"""Run all wf_* graphs locally via RunnerLoader (no Flask restart needed)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.runnables import RunnableConfig  # noqa: E402
from service.entity.runner import RunnerLoader  # noqa: E402
from utils.conversion import jsonify_state  # noqa: E402

GRAPHS = sorted((ROOT / "meta" / "graphs").glob("wf_*.json"))


def load_sample(gid: str) -> dict:
    path = ROOT / "tests" / gid / "sample.csv"
    if not path.is_file():
        return {"text": "Aspirin treats pain."}
    row = next(csv.DictReader(path.open(encoding="utf-8")))
    return dict(row)


def run_one(gid: str) -> tuple[bool, str]:
    params = jsonify_state(load_sample(gid))
    runner = RunnerLoader.load(gid)
    if not runner:
        return False, "runner not found"
    config: RunnableConfig = {"configurable": {"thread_id": f"local_{gid}"}}
    errors = []
    last = ""
    try:
        for chunk in runner.stream(
            params, config=config, stream_mode="updates", subgraphs=True
        ):
            if isinstance(chunk, tuple):
                _path, payload = chunk
                if isinstance(payload, dict):
                    for node, data in payload.items():
                        if isinstance(data, dict):
                            if data.get("error"):
                                errors.append(f"{node}: {data['error'][:120]}")
                            last = str(data)[:200]
            elif isinstance(chunk, dict):
                for node, data in chunk.items():
                    if isinstance(data, dict) and data.get("error"):
                        errors.append(f"{node}: {data['error'][:120]}")
    except Exception as ex:
        return False, str(ex)[:200]
    if errors:
        return False, "; ".join(errors[:3])
    return True, last or "ok"


def main() -> int:
    passed = failed = 0
    for p in GRAPHS:
        gid = p.stem
        ok, detail = run_one(gid)
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {gid}: {detail[:150]}")
        if ok:
            passed += 1
        else:
            failed += 1
    print(f"\nTotal {len(GRAPHS)}  Passed {passed}  Failed {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
