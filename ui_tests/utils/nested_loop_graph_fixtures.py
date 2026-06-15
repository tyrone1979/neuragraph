"""3-level nested loop; L3 loop body contains branch (≥2 arms) + nodes."""
from __future__ import annotations

from typing import Any

def nested_loop_graph_ids(stamp: str) -> dict[str, str]:
    return {
        "l3_body": f"rg_sg_l3_{stamp}",
        "l2_body": f"rg_sg_l2_{stamp}",
        "l1_body": f"rg_sg_l1_{stamp}",
        "main": f"rg_wf_nested_{stamp}",
    }


def build_nested_loop_graphs(stamp: str) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Return (graph_id -> meta, ids map).

    Topology:
      main (L1 outer_loop)
        → l1_body: mid_loop (L2)
            → l2_body: inner_loop (L3)
                → l3_body: line_branch (2 conditions) → report_format_json (both arms)
    """
    ids = nested_loop_graph_ids(stamp)
    l3, l2, l1, main = ids["l3_body"], ids["l2_body"], ids["l1_body"], ids["main"]

    graphs: dict[str, dict[str, Any]] = {
        l3: {
            "name": "Regression L3 loop body (branch inside)",
            "description": "Branch with 2 arms inside the innermost (L3) foreach body.",
            "nodes": [
                "START",
                "line_branch",
                "report_format_json",
                "END",
            ],
            "edges": [
                ["START", "line_branch"],
                ["line_branch", "report_format_json"],
                ["line_branch", "report_format_json"],
                ["report_format_json", "END"],
            ],
            "flowNodes": {
                "line_branch": {
                    "kind": "branch",
                    "name": "Line gate",
                    "conditions": [
                        {"label": "Has text", "field": "text", "op": "not_empty"},
                        {"label": "Empty text", "field": "text", "op": "empty"},
                    ],
                },
            },
            "bindings": {
                "report_format_json": {
                    "text": "{{ text }}",
                    "summary": "{{ route }}",
                },
            },
        },
        l2: {
            "name": "Regression L2 loop body",
            "description": "L3 foreach over lines (innermost loop).",
            "nodes": ["START", "inner_loop", "END"],
            "edges": [["START", "inner_loop"], ["inner_loop", "END"]],
            "flowNodes": {
                "inner_loop": {
                    "kind": "loop",
                    "name": "L3 lines loop",
                    "subgraphId": l3,
                    "loopConfig": {
                        "loopType": "foreach",
                        "array": "{{ lines }}",
                        "scalarItemField": "text",
                        "mergeKeys": ["result", "route", "filtered_entities"],
                    },
                },
            },
        },
        l1: {
            "name": "Regression L1 loop body",
            "description": "L2 foreach over parts.",
            "nodes": ["START", "mid_loop", "END"],
            "edges": [["START", "mid_loop"], ["mid_loop", "END"]],
            "flowNodes": {
                "mid_loop": {
                    "kind": "loop",
                    "name": "L2 parts loop",
                    "subgraphId": l2,
                    "loopConfig": {
                        "loopType": "foreach",
                        "array": "{{ parts }}",
                        "mergeKeys": ["result", "route", "filtered_entities"],
                    },
                },
            },
        },
        main: {
            "name": "Regression 3-level nested loops",
            "description": "L1 groups → L2 parts → L3 lines; branch inside L3 body.",
            "nodes": ["START", "outer_loop", "END"],
            "edges": [["START", "outer_loop"], ["outer_loop", "END"]],
            "flowNodes": {
                "outer_loop": {
                    "kind": "loop",
                    "name": "L1 groups loop",
                    "subgraphId": l1,
                    "loopConfig": {
                        "loopType": "foreach",
                        "array": "{{ groups }}",
                        "mergeKeys": ["result", "route", "filtered_entities"],
                    },
                },
            },
        },
    }
    return graphs, ids


NESTED_LOOP_TEST_INPUT: dict[str, Any] = {
    "groups": [
        {
            "parts": [
                {"lines": ["alpha", ""]},
                {"lines": ["beta"]},
            ]
        },
        {
            "parts": [
                {"lines": ["gamma"]},
            ]
        },
    ]
}


def verify_nested_loop_result(state: dict[str, Any]) -> tuple[bool, str]:
    """Assert branch routes and merged results after 3-level nested run."""
    route = state.get("route")
    if route is None:
        return False, "missing route (branch inside L3)"
    routes = route if isinstance(route, list) else [route]
    if "Empty text" not in routes:
        return False, f"expected Empty text branch, got routes={routes!r}"
    if "Has text" not in routes:
        return False, f"expected Has text branch, got routes={routes!r}"
    if len(routes) < 4:
        return False, f"expected >=4 L3 branch decisions (alpha,'',beta,gamma), got {len(routes)}"

    result = state.get("result")
    if not isinstance(result, dict):
        return False, "missing merged result dict"

    summary = result.get("summary")
    summary_blob = summary if isinstance(summary, list) else [summary]
    summary_text = " ".join(str(x) for x in summary_blob)
    if summary_text.count("Has text") < 1 or summary_text.count("Empty text") < 1:
        return False, f"branch labels missing in summaries: {summary!r}"

    original = result.get("original")
    original_blob = original if isinstance(original, list) else [original]
    original_text = " ".join(str(x) for x in original_blob)
    for token in ("alpha", "beta", "gamma"):
        if token not in original_text:
            return False, f"expected line {token!r} in result.original, got {original!r}"

    return True, f"routes={len(routes)} L3 branch+2 arms ok"
