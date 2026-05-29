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

from service.dataset_cid import (  # noqa: E402
    CID_REGISTRY,
    DEFAULT_NER_RUNNER,
    DEFAULT_RE_RUNNER,
    build_tuning_dataset,
    resolve_source_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, default=None)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--runner", default=DEFAULT_RE_RUNNER)
    parser.add_argument("--ner-runner", default=DEFAULT_NER_RUNNER)
    parser.add_argument("--out", default=CID_REGISTRY["runners"][DEFAULT_RE_RUNNER]["tuning"])
    parser.add_argument("--test-out", default=CID_REGISTRY["runners"][DEFAULT_RE_RUNNER]["test"])
    parser.add_argument("--write-test-remain", action="store_true")
    args = parser.parse_args()

    source = args.dev or CID_REGISTRY["source_raw"]
    try:
        resolve_source_path(source)
    except FileNotFoundError as ex:
        print(ex)
        return 1

    result = build_tuning_dataset(
        args.runner,
        source=source,
        size=args.size,
        tuning_out=args.out,
        test_out=args.test_out,
        write_test_remain=args.write_test_remain,
    )
    print(f"Wrote tuning dataset ({result['tuning_count']} rows):")
    print(f"  tests/{args.runner}/{result['tuning_output']}")
    print(f"  tests/{args.ner_runner}/{result['tuning_output']}")
    print(json.dumps(result.get("summary") or {}, ensure_ascii=False, indent=2))
    if result.get("test_output"):
        print(f"Wrote remaining test dataset ({result['test_count']} rows):")
        print(f"  tests/{args.runner}/{result['test_output']}")
        print(f"  tests/{args.ner_runner}/{result['test_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
