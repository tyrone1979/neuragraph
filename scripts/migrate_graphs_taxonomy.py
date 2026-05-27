"""
Rebuild meta/graphs: wf_* top-level workflows + sg_* subgraphs.
Run once: python scripts/migrate_graphs_taxonomy.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPHS = ROOT / "meta" / "graphs"

DELETE = {
    "ner_demo.json",
    "biomed_ner_graph.json",
    "bio_ner_graph.json",
    "demo_advanced_workflow.json",
    "nested_entity_extraction.json",
    "summarize_demo.json",
    "test_chain.json",
    "test_pipeline.json",
    "ner_4_doc_graph.json",
    "ner_4_doc_llm.json",
    "cid_workflow.json",
    "biomed_kg_workflow.json",
    "biomed_flair_kg_workflow.json",
    "biomed_re_workflow.json",
    "biomed_process_loop.json",
    "biomed_nested_loop.json",
    "re.json",
    "bt.json",
    "word_seg_comparison.json",
    "sub_ner.json",
    "sub_ner_llm.json",
    "sub_re.json",
    "sub_rv.json",
}

BRANCH_4_RE = [
    {"label": "Has entities", "field": "entities", "op": "not_empty"},
    {"label": "Has relations", "field": "relations", "op": "not_empty"},
    {"label": "Text only", "field": "text", "op": "not_empty"},
    {"label": "Skip downstream", "field": "entities", "op": "empty"},
]

BRANCH_4_CID_RE = [
    {"label": "Run full RE", "field": "entities", "op": "not_empty"},
    {"label": "Resolve synonyms", "field": "entities", "op": "contains", "value": "Chemical"},
    {"label": "Filter hypernyms", "field": "entities", "op": "contains", "value": "Disease"},
    {"label": "Skip RE", "field": "entities", "op": "empty"},
]

BRANCH_4_NER_ROUTE = [
    {"label": "Merge Flair results", "field": "entities", "op": "not_empty"},
    {"label": "LLM fallback NER", "field": "entities", "op": "empty"},
    {"label": "Long document", "field": "text", "op": "not_empty"},
    {"label": "Empty input", "field": "text", "op": "empty"},
]


def wf(
    gid: str,
    name: str,
    description: str,
    dataset: str,
    task: str,
    engine: str,
    flow_pattern: str,
    nodes: list,
    edges: list,
    bindings: dict | None = None,
    flow_nodes: dict | None = None,
) -> dict:
    g = {
        "id": gid,
        "name": name,
        "description": description,
        "dataset": dataset,
        "task": task,
        "engine": engine,
        "flow_pattern": flow_pattern,
        "nodes": ["START", *nodes, "END"],
        "edges": edges,
        "flowNodes": flow_nodes or {},
    }
    if bindings:
        g["bindings"] = bindings
    return g


def sg(gid: str, name: str, description: str, nodes: list, edges: list, bindings: dict | None = None, flow_nodes: dict | None = None) -> dict:
    return wf(gid, name, description, "internal", "subgraph", "mixed", "linear", nodes, edges, bindings, flow_nodes)


def build() -> dict[str, dict]:
    graphs = {}

    # ── Subgraphs ──
    graphs["sg_ner_flair_sent"] = sg(
        "sg_ner_flair_sent",
        "Sentence Flair NER",
        "Run ner_flair_sent on one sentence (loop body).",
        ["ner_flair_sent"],
        [["START", "ner_flair_sent"], ["ner_flair_sent", "END"]],
        {"ner_flair_sent": {"labels": "{{ labels }}", "sentence": "{{ sentence }}"}},
    )

    graphs["sg_ner_llm_tree"] = sg(
        "sg_ner_llm_tree",
        "Tree-based LLM NER",
        "syntax_dep_parse → ner_from_tree_llm per sentence.",
        ["syntax_dep_parse", "ner_from_tree_llm"],
        [
            ["START", "syntax_dep_parse"],
            ["syntax_dep_parse", "ner_from_tree_llm"],
            ["ner_from_tree_llm", "END"],
        ],
        {
            "syntax_dep_parse": {"sentence": "{{ sentence }}"},
            "ner_from_tree_llm": {"tree": "{{ syntax_dep_parse.tree }}", "labels": "{{ labels }}"},
        },
    )

    graphs["sg_re_tree"] = sg(
        "sg_re_tree",
        "Tree-based RE",
        "syntax_dep_parse → relation_from_tree_llm per sentence.",
        ["syntax_dep_parse", "relation_from_tree_llm"],
        [
            ["START", "syntax_dep_parse"],
            ["syntax_dep_parse", "relation_from_tree_llm"],
            ["relation_from_tree_llm", "END"],
        ],
        {"syntax_dep_parse": {"sentence": "{{ sentence }}"}, "relation_from_tree_llm": {"tree": "{{ syntax_dep_parse.tree }}"}},
    )

    graphs["sg_relation_verify"] = sg(
        "sg_relation_verify",
        "Relation verify pair",
        "relation_verify_llm → relation_verify_to_pair for one head/tail pair.",
        ["relation_verify_llm", "relation_verify_to_pair"],
        [
            ["START", "relation_verify_llm"],
            ["relation_verify_llm", "relation_verify_to_pair"],
            ["relation_verify_to_pair", "END"],
        ],
    )

    graphs["sg_preprocess_inner"] = sg(
        "sg_preprocess_inner",
        "Inner preprocess loop body",
        "Format / pass-through inner loop step.",
        ["report_format_json"],
        [["START", "report_format_json"], ["report_format_json", "END"]],
        {"report_format_json": {"text": "{{ text }}", "summary": "{{ text }}"}},
    )

    graphs["sg_re_preprocess"] = sg(
        "sg_re_preprocess",
        "RE preprocess + NER",
        "Nested inner loop then ner_llm (outer loop body for doc RE).",
        ["inner_preprocess_loop", "ner_llm"],
        [
            ["START", "inner_preprocess_loop"],
            ["inner_preprocess_loop", "ner_llm"],
            ["ner_llm", "END"],
        ],
        flow_nodes={
            "inner_preprocess_loop": {
                "kind": "loop",
                "name": "Inner preprocess loop",
                "subgraphId": "sg_preprocess_inner",
                "loopConfig": {"loopType": "foreach", "array": "{{ text }}"},
            }
        },
        bindings={
            "ner_llm": {"text": "{{ text }}", "labels": "Chemical, Disease"},
        },
    )

    # ── A. CID / doc NER eval ──
    graphs["wf_cid_ner_llm_eval"] = wf(
        "wf_cid_ner_llm_eval",
        "CID NER Eval (LLM)",
        "Chemical/Disease NER with LLM and generic metrics.",
        "cid",
        "ner",
        "llm",
        "linear",
        ["ner_llm", "eval_metrics"],
        [
            ["START", "ner_llm"],
            ["ner_llm", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        {
            "ner_llm": {"text": "{{ START.text }}", "labels": "Chemical, Disease"},
            "eval_metrics": {"expected": "{{ START.expected_entities }}", "predicted": "{{ ner_llm.entities }}"},
        },
    )

    graphs["wf_cid_ner_flair_eval"] = wf(
        "wf_cid_ner_flair_eval",
        "CID NER Eval (Flair doc)",
        "Document-level Flair NER with metrics.",
        "cid",
        "ner",
        "flair",
        "linear",
        ["ner_flair_doc", "eval_metrics"],
        [
            ["START", "ner_flair_doc"],
            ["ner_flair_doc", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        {
            "ner_flair_doc": {"text": "{{ START.text }}", "labels": "Chemical,Disease"},
            "eval_metrics": {"expected": "{{ START.expected_entities }}", "predicted": "{{ ner_flair_doc.entities }}"},
        },
    )

    graphs["wf_doc_ner_llm_eval"] = wf(
        "wf_doc_ner_llm_eval",
        "Doc NER Eval (LLM)",
        "Split document then LLM NER with metrics.",
        "doc_ner",
        "ner",
        "llm",
        "linear",
        ["text_sentence_split", "ner_llm", "eval_metrics"],
        [
            ["START", "text_sentence_split"],
            ["text_sentence_split", "ner_llm"],
            ["ner_llm", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        {
            "ner_llm": {"text": "{{ START.text }}", "labels": "{{ START.labels }}"},
            "eval_metrics": {"expected": "{{ START.expected_entities }}", "predicted": "{{ ner_llm.entities }}"},
        },
    )

    graphs["wf_doc_ner_flair_eval"] = wf(
        "wf_doc_ner_flair_eval",
        "Doc NER Eval (Flair)",
        "Document Flair NER with metrics (replaces bio_ner_graph).",
        "doc_ner",
        "ner",
        "flair",
        "linear",
        ["ner_flair_doc", "eval_metrics"],
        [
            ["START", "ner_flair_doc"],
            ["ner_flair_doc", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        {
            "ner_flair_doc": {"text": "{{ START.text }}", "labels": "{{ START.labels }}"},
            "eval_metrics": {"expected": "{{ START.expected_entities }}", "predicted": "{{ ner_flair_doc.entities }}"},
        },
    )

    # ── B. CID RE ──
    graphs["wf_cid_re_llm_linear"] = wf(
        "wf_cid_re_llm_linear",
        "CID RE Pipeline (linear)",
        "NER → LLM synonym resolve → LLM hypernym filter → relation extract (metrics via Metrics plugin at persistence).",
        "cid",
        "re",
        "llm",
        "linear",
        ["ner_llm", "ontology_synonym_resolve", "ontology_hypernym_filter", "relation_extract_llm"],
        [
            ["START", "ner_llm"],
            ["ner_llm", "ontology_synonym_resolve"],
            ["ontology_synonym_resolve", "ontology_hypernym_filter"],
            ["ontology_hypernym_filter", "relation_extract_llm"],
            ["relation_extract_llm", "END"],
        ],
        {
            "ner_llm": {"text": "{{ START.text }}", "labels": "Chemical, Disease"},
            "ontology_synonym_resolve": {
                "text": "{{ START.text }}",
                "entities": "{{ ner_llm.entities }}",
            },
            "ontology_hypernym_filter": {
                "entities": "{{ ner_llm.entities }}",
                "synonyms": "{{ ontology_synonym_resolve.synonyms }}",
            },
            "relation_extract_llm": {
                "text": "{{ START.text }}",
                "entities": "{{ ontology_hypernym_filter.filtered_entities }}",
            },
        },
    )

    graphs["wf_cid_re_branch"] = wf(
        "wf_cid_re_branch",
        "CID RE (multi-branch gate)",
        "NER then 4-way branch gate before relation extraction.",
        "cid",
        "re",
        "llm",
        "branch",
        ["ner_llm", "cid_re_gate", "relation_extract_llm", "ontology_synonym_resolve", "eval_metrics_relation"],
        [
            ["START", "ner_llm"],
            ["ner_llm", "cid_re_gate"],
            ["cid_re_gate", "relation_extract_llm"],
            ["cid_re_gate", "ontology_synonym_resolve"],
            ["cid_re_gate", "eval_metrics_relation"],
            ["relation_extract_llm", "eval_metrics_relation"],
            ["ontology_synonym_resolve", "eval_metrics_relation"],
            ["eval_metrics_relation", "END"],
        ],
        flow_nodes={
            "cid_re_gate": {
                "kind": "branch",
                "name": "CID RE Gate",
                "conditions": BRANCH_4_CID_RE,
            }
        },
        bindings={
            "ner_llm": {"text": "{{ START.text }}", "labels": "Chemical, Disease"},
            "relation_extract_llm": {"text": "{{ START.text }}", "entities": "{{ ner_llm.entities }}"},
            "ontology_synonym_resolve": {"entities": "{{ ner_llm.entities }}"},
        },
    )

    # ── C. Doc NER loop + multi-branch ──
    graphs["wf_doc_ner_loop_branch"] = wf(
        "wf_doc_ner_loop_branch",
        "Doc NER loop + branch",
        "Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics.",
        "doc_ner",
        "ner",
        "mixed",
        "loop_branch",
        ["text_sentence_split", "ner_sentence_loop", "ner_route", "ner_llm", "eval_metrics"],
        [
            ["START", "text_sentence_split"],
            ["text_sentence_split", "ner_sentence_loop"],
            ["ner_sentence_loop", "ner_route"],
            ["ner_route", "ner_llm"],
            ["ner_route", "eval_metrics"],
            ["ner_llm", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        flow_nodes={
            "ner_sentence_loop": {
                "kind": "loop",
                "name": "Sentence NER loop",
                "subgraphId": "sg_ner_flair_sent",
                "loopConfig": {"loopType": "foreach", "array": "{{ sentences }}"},
            },
            "ner_route": {
                "kind": "branch",
                "name": "NER Route",
                "conditions": BRANCH_4_NER_ROUTE,
            },
        },
        bindings={
            "ner_llm": {"text": "{{ START.text }}", "labels": "{{ START.labels }}"},
            "eval_metrics": {"expected": "{{ START.expected_entities }}", "predicted": "{{ ner_llm.entities }}"},
        },
    )

    # ── D. Doc RE nested + multi-branch ──
    graphs["wf_doc_re_nested_branch"] = wf(
        "wf_doc_re_nested_branch",
        "Doc RE (nested loop + branch)",
        "Outer loop with nested preprocess + NER, 4-way branch, then RE.",
        "doc_re",
        "re",
        "llm",
        "branch_nested_loop",
        ["re_process_loop", "re_gate", "relation_extract_llm", "eval_metrics", "kg_triple_merge"],
        [
            ["START", "re_process_loop"],
            ["re_process_loop", "re_gate"],
            ["re_gate", "relation_extract_llm"],
            ["re_gate", "eval_metrics"],
            ["re_gate", "kg_triple_merge"],
            ["relation_extract_llm", "END"],
            ["eval_metrics", "END"],
            ["kg_triple_merge", "END"],
        ],
        flow_nodes={
            "re_process_loop": {
                "kind": "loop",
                "name": "RE Processing Loop",
                "subgraphId": "sg_re_preprocess",
                "loopConfig": {"loopType": "foreach", "array": "{{ text }}"},
            },
            "re_gate": {
                "kind": "branch",
                "name": "RE Route Gate",
                "conditions": BRANCH_4_RE,
            },
        },
        bindings={
            "relation_extract_llm": {
                "text": "{{ re_gate.text }}",
                "entities": "{{ re_process_loop.entities }}",
            },
        },
    )

    # ── E. RE verify loop ──
    graphs["wf_re_verify_llm_loop"] = wf(
        "wf_re_verify_llm_loop",
        "RE Verify (pair loop)",
        "Generate evaluation pairs → loop verify subgraph → metrics.",
        "re_verify",
        "re_verify",
        "llm",
        "loop",
        ["eval_pair_generate", "verify_pairs_loop", "eval_metrics"],
        [
            ["START", "eval_pair_generate"],
            ["eval_pair_generate", "verify_pairs_loop"],
            ["verify_pairs_loop", "eval_metrics"],
            ["eval_metrics", "END"],
        ],
        flow_nodes={
            "verify_pairs_loop": {
                "kind": "loop",
                "name": "Verify each pair",
                "subgraphId": "sg_relation_verify",
                "loopConfig": {"loopType": "foreach", "array": "{{ pairs }}"},
            }
        },
        bindings={
            "eval_pair_generate": {"expected_entities": "{{ START.expected_entities }}"},
            "eval_metrics": {"expected": "{{ START.expected_relations }}"},
        },
    )

    # ── F. KG ──
    graphs["wf_kg_llm_full"] = wf(
        "wf_kg_llm_full",
        "KG Build (LLM NER)",
        "LLM NER → entity link → RE → triple merge → RDF export.",
        "kg",
        "kg",
        "llm",
        "linear",
        ["ner_llm", "ontology_entity_link", "relation_extract_llm", "kg_triple_merge", "kg_rdf_export"],
        [
            ["START", "ner_llm"],
            ["ner_llm", "ontology_entity_link"],
            ["ontology_entity_link", "relation_extract_llm"],
            ["relation_extract_llm", "kg_triple_merge"],
            ["kg_triple_merge", "kg_rdf_export"],
            ["kg_rdf_export", "END"],
        ],
        bindings={
            "ner_llm": {"text": "{{ START.text }}", "labels": "Chemical, Disease"},
            "ontology_entity_link": {"entities": "{{ ner_llm.entities }}"},
            "relation_extract_llm": {"text": "{{ START.text }}", "entities": "{{ ner_llm.entities }}"},
            "kg_triple_merge": {
                "relations": "{{ relation_extract_llm.relations }}",
                "entity_link": "{{ ontology_entity_link.entity_link }}",
            },
        },
    )

    graphs["wf_kg_flair_full"] = wf(
        "wf_kg_flair_full",
        "KG Build (Flair NER)",
        "Flair doc NER → entity link → triple extract → merge → RDF.",
        "kg",
        "kg",
        "mixed",
        "linear",
        ["ner_flair_doc", "ontology_entity_link", "kg_triple_extract_llm", "kg_triple_merge", "kg_rdf_export"],
        [
            ["START", "ner_flair_doc"],
            ["ner_flair_doc", "ontology_entity_link"],
            ["ontology_entity_link", "kg_triple_extract_llm"],
            ["kg_triple_extract_llm", "kg_triple_merge"],
            ["kg_triple_merge", "kg_rdf_export"],
            ["kg_rdf_export", "END"],
        ],
        bindings={
            "ner_flair_doc": {"labels": "Chemical,Disease"},
            "ontology_entity_link": {"entities": "{{ ner_flair_doc.entities }}"},
            "kg_triple_extract_llm": {"text": "{{ START.text }}", "entities": "{{ ner_flair_doc.entities }}"},
            "kg_triple_merge": {
                "relations": "{{ kg_triple_extract_llm.triples }}",
                "entity_link": "{{ ontology_entity_link.entity_link }}",
            },
        },
    )

    graphs["wf_kg_syntax_loop"] = wf(
        "wf_kg_syntax_loop",
        "KG from syntax (sentence loop)",
        "Coreference → split → loop tree-RE subgraph → CSV persist.",
        "kg_triple",
        "kg",
        "llm",
        "loop",
        ["text_coreference", "text_sentence_split", "sentence_re_loop", "kg_triple_persist"],
        [
            ["START", "text_coreference"],
            ["text_coreference", "text_sentence_split"],
            ["text_sentence_split", "sentence_re_loop"],
            ["sentence_re_loop", "kg_triple_persist"],
            ["kg_triple_persist", "END"],
        ],
        flow_nodes={
            "sentence_re_loop": {
                "kind": "loop",
                "name": "RE per sentence",
                "subgraphId": "sg_re_tree",
                "loopConfig": {"loopType": "foreach", "array": "{{ sentences }}"},
            }
        },
        bindings={"text_sentence_split": {"text": "{{ text_coreference.text }}"}},
    )

    # ── G. Other ──
    graphs["wf_word_seg_llm_eval"] = wf(
        "wf_word_seg_llm_eval",
        "Word Segmentation Eval",
        "LLM word segmentation with boundary metrics.",
        "word_seg",
        "segment",
        "llm",
        "linear",
        ["text_word_segment", "eval_metrics_segment"],
        [
            ["START", "text_word_segment"],
            ["text_word_segment", "eval_metrics_segment"],
            ["eval_metrics_segment", "END"],
        ],
    )

    graphs["wf_general_report_linear"] = wf(
        "wf_general_report_linear",
        "Summarize + format",
        "Summarize text and pack into JSON result.",
        "general",
        "report",
        "llm",
        "linear",
        ["text_summarize", "report_format_json"],
        [
            ["START", "text_summarize"],
            ["text_summarize", "report_format_json"],
            ["report_format_json", "END"],
        ],
        {"report_format_json": {"text": "{{ START.text }}", "summary": "{{ text_summarize.summary }}"}},
    )

    return graphs


def main():
    for name in DELETE:
        p = GRAPHS / name
        if p.is_file():
            p.unlink()
            print(f"deleted {name}")

    graphs = build()
    for gid, data in sorted(graphs.items()):
        path = GRAPHS / f"{gid}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"write {gid}.json")

    print(f"Total graphs: {len(graphs)}")


if __name__ == "__main__":
    main()
