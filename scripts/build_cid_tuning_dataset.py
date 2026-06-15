#!/usr/bin/env python3
"""Build a small stratified CID tuning dataset from dev.txt (PubTator + gold)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.dataset.registry import require_catalog  # noqa: E402

DEFAULT_SOURCE = "data/raw/dev.txt"
DEFAULT_AGENT = "wf_cid_re_llm_linear"
DEFAULT_NER_AGENT = "wf_cid_ner_llm_eval"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, default=None)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--ner-agent", default=DEFAULT_NER_AGENT)
    parser.add_argument("--format", default="re")
    parser.add_argument("--out", default="cid_dev_tuning_stratified.csv")
    parser.add_argument("--test-out", default="cid_dev_test_remain.csv")
    parser.add_argument("--write-test-remain", action="store_true")
    parser.add_argument("--mirror-ner", action="store_true")
    args = parser.parse_args()

    catalog = require_catalog()
    source = str(args.dev or DEFAULT_SOURCE)
    try:
        catalog.resolve_source(source)
    except FileNotFoundError as ex:
        print(ex)
        return 1

    mirror = [{"agent_id": args.ner_agent, "format": "ner"}] if args.mirror_ner else None
    result = catalog.build_tuning(
        args.agent,
        source=source,
        format=args.format,
        size=args.size,
        tuning_out=args.out,
        test_out=args.test_out,
        write_test_remain=args.write_test_remain,
        mirror=mirror,
    )
    print(f"Wrote tuning dataset ({result['tuning_count']} rows):")
    print(f"  tests/{args.agent}/{result['tuning_output']}")
    if args.mirror_ner:
        print(f"  tests/{args.ner_agent}/{result['tuning_output']}")
    print(json.dumps(result.get("summary") or {}, ensure_ascii=False, indent=2))
    if result.get("test_output"):
        print(f"Wrote remaining test dataset ({result['test_count']} rows):")
        print(f"  tests/{args.agent}/{result['test_output']}")
        if args.mirror_ner:
            print(f"  tests/{args.ner_agent}/{result['test_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
