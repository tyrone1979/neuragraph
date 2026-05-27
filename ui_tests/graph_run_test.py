"""Run every workflow graph via /stream/test; expect [DONE]."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from ui_tests.common import fail, goto, ok, shot
from ui_tests.graph_utils import ALL_GRAPH_IDS, list_graph_ids

GRAPH_INPUTS: dict[str, dict] = {
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
    },
    "wf_cid_re_branch": {
        "text": "Aspirin may cause headache.",
        "labels": "Chemical,Disease",
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
    "sg_ner_flair_sent": {"sentence": "Aspirin treats pain.", "labels": "Chemical,Disease"},
    "sg_ner_llm_tree": {"sentence": "Aspirin treats pain.", "labels": "Chemical,Disease"},
    "sg_re_tree": {"sentence": "Aspirin treats pain."},
    "sg_relation_verify": {
        "text": "Aspirin may cause headache.",
        "head": "Aspirin",
        "tail": "headache",
        "entity_link": json.dumps({"Aspirin": "Aspirin", "headache": "headache"}),
    },
    "sg_preprocess_inner": {"text": "Sample line."},
    "sg_re_preprocess": {"text": "Aspirin treats pain."},
}

LLM_GRAPH_TIMEOUT = 420
FAST_GRAPH_TIMEOUT = 90
SNAPSHOT_GRAPHS = frozenset(
    {
        "wf_doc_re_nested_branch",
        "wf_doc_ner_flair_eval",
        "wf_cid_re_branch",
        "sg_ner_flair_sent",
    }
)


def wait_stream_done(base: str, graph_id: str, params: dict, timeout: int) -> tuple[bool, str]:
    q = urllib.parse.urlencode({"graphId": graph_id, **params})
    url = f"{base}/stream/test?{q}"
    buf = ""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace")
                if "[DONE]" in line:
                    return True, buf
                if line.startswith("data: "):
                    buf += line[6:].replace("\\n", "\n")[:500]
    except Exception as ex:
        return False, str(ex)[:200]
    return False, buf[:200] or "no DONE"


def run(page: Page, base: str, screenshots_dir: str, tests_data_dir: Path) -> None:
    on_disk = set(list_graph_ids(from_backup=False))
    missing = [g for g in ALL_GRAPH_IDS if g not in on_disk]
    if missing:
        fail("G4-preflight", f"missing graphs: {missing[:5]}")
        return

    print("\n=== G4. RUN ALL GRAPHS (SSE /stream/test) ===")
    for gid in ALL_GRAPH_IDS:
        params = GRAPH_INPUTS.get(gid, {"text": "Aspirin treats pain."})
        timeout = LLM_GRAPH_TIMEOUT if gid.startswith("wf_") else FAST_GRAPH_TIMEOUT
        print(f"  Running {gid} (timeout={timeout}s)...")
        done, detail = wait_stream_done(base, gid, params, timeout=timeout)
        if done:
            ok(f"G4-{gid}", "DONE")
        else:
            fail(f"G4-{gid}", detail)

    # UI snapshots after SSE (fresh navigation)
    for gid in SNAPSHOT_GRAPHS:
        if gid not in on_disk:
            continue
        params = GRAPH_INPUTS.get(gid, {"text": "Aspirin treats pain."})
        try:
            goto(page, base, f"/graph/{gid}/edit", 2)
            page.evaluate(
                """(params) => {
                    if (typeof openTestModal === 'function') openTestModal();
                    const ta = document.getElementById('testInput');
                    if (ta) ta.value = JSON.stringify(params, null, 2);
                }""",
                params,
            )
            time.sleep(0.5)
            shot(page, screenshots_dir, f"g4_test_modal_{gid}")
        except Exception as ex:
            fail(f"G4-shot-{gid}", str(ex)[:100])

    try:
        goto(page, base, "/graph/", 2)
        shot(page, screenshots_dir, "g4_00_graph_list")
    except Exception:
        pass
