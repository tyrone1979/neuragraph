#!/usr/bin/env python3
"""Step-by-step stream diagnostic for wf_cid_re_llm_linear (no Playwright)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.runnables import RunnableConfig  # noqa: E402
from plugin.plugin_loader import get_plugin  # noqa: E402
from service.entity.runner import RunnerLoader  # noqa: E402
from service.entity.test import TestLoader  # noqa: E402
from utils.conversion import jsonify_state  # noqa: E402

RUNNER = "wf_cid_re_llm_linear"


def _pair_estimate(entities) -> int:
    if isinstance(entities, str):
        entities = json.loads(entities)
    if not isinstance(entities, list):
        return 0
    chem, dis = set(), set()
    for e in entities:
        if not isinstance(e, dict):
            continue
        eid = e.get("id") or ""
        lbl = e.get("label") or ""
        if not eid:
            continue
        if lbl == "Chemical":
            chem.add(eid)
        elif lbl == "Disease":
            dis.add(eid)
    return len(chem) * len(dis)


def _summarize(node: str, update: dict) -> str:
    if not isinstance(update, dict):
        return str(update)[:200]
    parts = []
    for k, v in update.items():
        if k == "filtered_entities" and isinstance(v, list):
            parts.append(f"filtered_entities={len(v)}")
        elif k == "pairs" and isinstance(v, list):
            parts.append(f"pairs={len(v)}")
        elif k == "relations":
            parts.append(f"relations={v!r}"[:120])
        elif k == "result":
            parts.append(f"result={v!r}"[:40])
        elif k == "error":
            parts.append(f"ERROR={v!r}"[:200])
        else:
            parts.append(f"{k}={type(v).__name__}")
    return ", ".join(parts) or "(empty update)"


def main() -> int:
    row = TestLoader.workflow_test_input(RUNNER)
    if not row:
        print("No tests/wf_cid_re_llm_linear/sample.csv")
        return 1
    row = jsonify_state(dict(row))
    print(f"=== diag {RUNNER} ===", flush=True)
    print(f"text chars: {len(row.get('text', ''))}", flush=True)
    print(f"entities: {len(row.get('entities') or [])}", flush=True)
    print(f"est. C-D pairs after pair_generate: {_pair_estimate(row.get('entities'))}", flush=True)
    print(f"gold: {row.get('gold_relations')}", flush=True)

    runner = RunnerLoader.load(RUNNER)
    config: RunnableConfig = {"configurable": {"thread_id": f"diag_{int(time.time())}"}}
    t0 = time.perf_counter()
    step = 0

    try:
        for chunk in runner.stream(
            row, config=config, stream_mode="updates", subgraphs=True
        ):
            step += 1
            now = time.perf_counter()
            if isinstance(chunk, tuple) and len(chunk) == 2:
                path, payload = chunk
                path_s = " / ".join(str(p) for p in path) if path else "?"
            else:
                path_s = "?"
                payload = chunk
            if isinstance(payload, dict):
                for node, update in payload.items():
                    print(
                        f"[{now - t0:7.1f}s] step={step} path={path_s} node={node} | {_summarize(node, update)}",
                        flush=True,
                    )
                    if isinstance(update, dict):
                        if update.get("pairs"):
                            print(
                                f"         pairs detail: {json.dumps(update['pairs'], ensure_ascii=False)[:500]}",
                                flush=True,
                            )
            else:
                print(f"[{now - t0:7.1f}s] step={step} raw chunk type={type(chunk).__name__}", flush=True)
    except Exception as ex:
        print(f"STREAM EXCEPTION after {time.perf_counter() - t0:.1f}s: {ex!r}", flush=True)
        raise

    total = time.perf_counter() - t0
    print(f"\nDONE {step} stream steps in {total:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
