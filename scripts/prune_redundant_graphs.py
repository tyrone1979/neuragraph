#!/usr/bin/env python3
"""Remove redundant workflow JSON (keep highest version per family)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.graphutils import redundant_graph_ids, select_representative_graph_ids  # noqa: E402

GRAPHS = ROOT / "meta" / "graphs"
BACKUP = ROOT / "meta" / "graphs_backup"
TESTS = ROOT / "tests"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be removed without deleting",
    )
    parser.add_argument(
        "--tests-dirs",
        action="store_true",
        help="Also remove tests/<runner_id>/ for redundant graphs",
    )
    args = parser.parse_args()

    keep = select_representative_graph_ids()
    drop = redundant_graph_ids()
    print(f"Keep {len(keep)} graphs; remove {len(drop)} redundant")
    for gid in drop:
        print(f"  - {gid}")

    if args.dry_run:
        return 0

    for gid in drop:
        for base in (GRAPHS, BACKUP):
            path = base / f"{gid}.json"
            if path.is_file():
                path.unlink()
        if args.tests_dirs:
            td = TESTS / gid
            if td.is_dir():
                shutil.rmtree(td)

    # Refresh backup to match pruned live set
    BACKUP.mkdir(parents=True, exist_ok=True)
    for p in list(BACKUP.glob("*.json")):
        p.unlink()
    for p in GRAPHS.glob("*.json"):
        shutil.copy2(p, BACKUP / p.name)

    print(f"Done. {len(list(GRAPHS.glob('*.json')))} graphs under meta/graphs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
