"""Playwright regression: representative experiment runs — 2 articles, gold/no_gold, tuning, baseline screenshots."""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.utils.playwright_helpers import fail, goto, ok, shot
from ui_tests.utils.regression_helpers import (
    all_graph_ids,
    run_graph_experiment,
    safe_name,
)

# graph_id, with_gold, with_tuning — covers subgraph / e2e subgraph / main workflow
DEFAULT_REP_EXP_CASES: list[tuple[str, bool, bool]] = [
    ("sg_cid_re_verify", True, False),
    ("sg_cid_re_verify", False, True),
    ("sg_e2e_cid_re", True, False),
    ("wf_e2e_flair_opt_re", True, False),
    ("wf_e2e_flair_opt_re", False, False),
    ("wf_e2e_flair_opt_re", True, True),
]

ALL_VARIANTS = (
    (True, False),
    (True, True),
    (False, False),
    (False, True),
)


def _clear_screenshots(screenshots_dir: str) -> None:
    root = Path(screenshots_dir)
    if not root.is_dir():
        return
    removed = sum(1 for p in root.iterdir() if p.is_file() and p.unlink(missing_ok=True) is None)
    print(f"[regression-exp] cleared {removed} file(s) from {root}")


def _resolve_exp_cases(all_ids: list[str]) -> list[tuple[str, bool, bool]]:
    only = (os.environ.get("NG_REGRESSION_EXP_ONLY") or os.environ.get("NG_GRAPH_ONLY") or "").strip()
    if only:
        if only not in all_ids:
            return []
        return [(only, gold, tune) for gold, tune in ALL_VARIANTS]

    if os.environ.get("NG_REGRESSION_EXP_ALL", "").strip().lower() in ("1", "true", "yes"):
        return [(gid, gold, tune) for gid in all_ids for gold, tune in ALL_VARIANTS]

    custom = (os.environ.get("NG_REGRESSION_EXP_GRAPHS") or "").strip()
    if custom:
        graph_ids = [g.strip() for g in custom.split(",") if g.strip()]
        graph_ids = [g for g in graph_ids if g in all_ids]
        return [(gid, gold, tune) for gid in graph_ids for gold, tune in ALL_VARIANTS]

    known = set(all_ids)
    cases = [c for c in DEFAULT_REP_EXP_CASES if c[0] in known]
    if cases:
        return cases

    # Fallback: first graph, two variants
    if not all_ids:
        return []
    gid = all_ids[0]
    return [(gid, True, False), (gid, False, False)]


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    if os.environ.get("NG_EXP_NO_CLEAR", "").strip().lower() not in ("1", "true", "yes"):
        _clear_screenshots(screenshots_dir)

    all_ids = all_graph_ids(from_backup=False)
    cases = _resolve_exp_cases(all_ids)
    if not cases:
        fail("REXP-setup", "no representative exp cases (check meta/graphs)")
        return

    graphs = sorted({c[0] for c in cases})
    print(
        f"\n=== REXP: {len(cases)} representative run(s), "
        f"{len(graphs)} graph(s), 2 articles, config + baseline screenshots ==="
    )
    for gid in graphs:
        print(f"  graph: {gid}")
    goto(page, base, "/exp/", 2)
    shot(page, screenshots_dir, "rexp_exp_list_start")

    timeout = int(os.environ.get("NG_REGRESSION_EXP_TIMEOUT", "420"))
    for run_idx, (graph_id, with_gold, with_tuning) in enumerate(cases, start=1):
        gold_tag = "gold" if with_gold else "no_gold"
        tune_tag = "with_tuning" if with_tuning else "test_only"
        print(
            f"\n--- REXP [{run_idx}/{len(cases)}] {graph_id} "
            f"variant={gold_tag}/{tune_tag} timeout={timeout}s ---"
        )
        try:
            run_graph_experiment(
                page,
                base,
                screenshots_dir,
                graph_id,
                with_gold=with_gold,
                with_tuning=with_tuning,
                timeout=timeout,
            )
        except Exception as ex:
            fail(f"REXP-{safe_name(graph_id)}-{gold_tag}_{tune_tag}", str(ex)[:200])

    ok("REXP-summary", f"processed {len(cases)} representative run(s)")
    goto(page, base, "/exp/", 2)
    shot(page, screenshots_dir, "rexp_exp_list_end")
