"""
Migrate meta/agents to layer + engine taxonomy and rename IDs.
Also rewrites node references in meta/graphs/*.json.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "meta" / "agents"
GRAPHS = ROOT / "meta" / "graphs"

# old_id -> new_id (merged agents map to single target)
RENAME = {
    "sentence_split": "text_sentence_split",
    "word_segmentation": "text_word_segment",
    "coreference_resolution": "text_coreference",
    "summarize_text": "text_summarize",
    "dependency_parse": "syntax_dep_parse",
    "biomed_ner": "ner_llm",
    "ner_extractor": "ner_llm",
    "gene_protein_ner": "ner_llm",
    "cid_ner": "ner_llm",
    "bio_ner": "ner_flair_sent",
    "biomed_flair_doc_ner": "ner_flair_doc",
    "entity_extract": "ner_from_tree_llm",
    "biomed_relation_extract": "relation_extract_llm",
    "cid_re": "relation_extract_llm",
    "relation_extraction": "relation_from_tree_llm",
    "cid_re_verify": "relation_verify_llm",
    "re_verify_pair_builder": "relation_verify_to_pair",
    "synonym_extraction": "ontology_synonym_extract",
    "cid_synonym_resolve": "ontology_synonym_resolve",
    "hypernym_identification": "ontology_hypernym_identify",
    "cid_hypernym_filter": "ontology_hypernym_filter",
    "kg_entity_linker": "ontology_entity_link",
    "kg_triple_extractor": "kg_triple_extract_llm",
    "kg_triple_merger": "kg_triple_merge",
    "bt_persistence": "kg_triple_persist",
    "metrics": "eval_metrics",
    "word_seg_metrics": "eval_metrics_segment",
    "cid_metrics": "eval_metrics_relation",
    "create_evaluation_pairs": "eval_pair_generate",
    "make_report": "report_experiment",
    "format_json": "report_format_json",
    "dti_analyzer": "relation_dti_analyze",
}

DELETE_IDS = {
    "sub_ner",
    "sub_ner_llm",
    "sub_re",
    "sub_rv",
    "map_cid_txt_4_ner",
    "map_cid_to_re_field",
    "relation_result_to_pair",
    "test_upper",
    "test_split",
    "test_count",
    "biomed_re_branch",
    "ner_with_tool",
}

TARGET_IDS = {
    "text_sentence_split",
    "text_word_segment",
    "text_coreference",
    "text_summarize",
    "syntax_dep_parse",
    "ner_llm",
    "ner_flair_sent",
    "ner_flair_doc",
    "ner_from_tree_llm",
    "relation_extract_llm",
    "relation_from_tree_llm",
    "relation_verify_llm",
    "relation_verify_to_pair",
    "relation_dti_analyze",
    "ontology_synonym_extract",
    "ontology_synonym_resolve",
    "ontology_hypernym_identify",
    "ontology_hypernym_filter",
    "ontology_entity_link",
    "kg_triple_extract_llm",
    "kg_triple_merge",
    "kg_rdf_export",
    "kg_triple_persist",
    "eval_metrics",
    "eval_metrics_segment",
    "eval_metrics_relation",
    "eval_pair_generate",
    "report_experiment",
    "report_format_json",
}


def load_agent(aid: str) -> dict | None:
    p = AGENTS / f"{aid}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def base_meta(layer: str, engine: str, **extra) -> dict:
    m = {"layer": layer, "engine": engine}
    m.update(extra)
    return m


def build_agents() -> dict[str, dict]:
    """new_id -> full agent config"""
    out: dict[str, dict] = {}

    def put(aid: str, cfg: dict):
        cfg = deepcopy(cfg)
        cfg["id"] = aid
        out[aid] = cfg

    # --- document ---
    for old, new in [
        ("sentence_split", "text_sentence_split"),
        ("word_segmentation", "text_word_segment"),
        ("coreference_resolution", "text_coreference"),
        ("summarize_text", "text_summarize"),
    ]:
        src = load_agent(old)
        if src:
            put(
                new,
                {
                    **src,
                    **base_meta("document", "llm"),
                    "name": {
                        "text_sentence_split": "Sentence Split (LLM)",
                        "text_word_segment": "Word Segmentation (LLM)",
                        "text_coreference": "Coreference Resolution (LLM)",
                        "text_summarize": "Text Summarization (LLM)",
                    }[new],
                    "description": {
                        "text_sentence_split": "Split text into a JSON array of sentences.",
                        "text_word_segment": "Medical/clinical tokenization with explicit delimiters.",
                        "text_coreference": "Resolve pronouns and return substituted full text.",
                        "text_summarize": "Produce a short summary of the input text.",
                    }[new],
                },
            )

    src = load_agent("dependency_parse")
    if src:
        put(
            "syntax_dep_parse",
            {
                **src,
                **base_meta("syntax", "llm"),
                "name": "Dependency Parse (CoNLL-U)",
                "description": "Convert a sentence to CoNLL-U dependency tree.",
            },
        )

    # --- ner ---
    ner_llm = load_agent("ner_extractor") or load_agent("biomed_ner") or {}
    put(
        "ner_llm",
        {
            **ner_llm,
            "type": "LLM",
            "model": ner_llm.get("model", "deepseek"),
            "inputs": ["text", "labels"],
            "outputs": {"name": "entities", "type": "dict"},
            **base_meta(
                "ner",
                "llm",
                granularity="document",
                entity_types=["Chemical", "Disease"],
                default_labels="Chemical, Disease",
            ),
            "name": "NER (LLM, configurable types)",
            "description": "Extract entities for configurable types via {labels} or default entity_types in metadata.",
            "prompt_template": ner_llm.get(
                "prompt_template",
                {
                    "description": "Configurable NER",
                    "system": "You are an NER system. Output valid JSON only.",
                    "human": "Text: {text}\n\nEntity types: {labels}\n\nReturn JSON with types as keys and mention lists as values.",
                },
            ),
        },
    )

    flair_sent = load_agent("bio_ner")
    if flair_sent:
        put(
            "ner_flair_sent",
            {
                **flair_sent,
                **base_meta("ner", "flair", granularity="sentence"),
                "name": "NER (Flair, sentence)",
                "description": "HunFlair2 tagging on a single sentence; labels comma-separated or list.",
            },
        )

    flair_doc = load_agent("biomed_flair_doc_ner")
    if flair_doc:
        put(
            "ner_flair_doc",
            {
                **flair_doc,
                **base_meta("ner", "flair", granularity="document"),
                "name": "NER (Flair, document)",
                "description": "Split document into sentences, run Flair per sentence, aggregate by label.",
            },
        )

    tree_ner = load_agent("entity_extract")
    if tree_ner:
        put(
            "ner_from_tree_llm",
            {
                **tree_ner,
                **base_meta("ner", "llm", granularity="sentence", requires=["tree"]),
                "name": "NER from Dependency Tree (LLM)",
                "description": "Extract entities from a CoNLL-U tree for given label types.",
            },
        )

    # --- relation ---
    rel_ext = load_agent("biomed_relation_extract") or {}
    put(
        "relation_extract_llm",
        {
            **rel_ext,
            "type": "LLM",
            "model": rel_ext.get("model", "deepseek"),
            "inputs": ["text", "entities"],
            "outputs": {"name": "relations", "type": "list"},
            **base_meta("relation", "llm", relation_mode="extract"),
            "name": "Relation Extraction (LLM)",
            "description": "Extract relations from text and entity context. One relation per line: head | predicate | tail.",
            "prompt_template": rel_ext.get("prompt_template", {}),
            "alternate_inputs": {"filtered_entities": "entities"},
        },
    )

    rel_tree = load_agent("relation_extraction")
    if rel_tree:
        put(
            "relation_from_tree_llm",
            {
                **rel_tree,
                **base_meta("relation", "llm", relation_mode="from_tree"),
                "name": "Relation Extraction from Tree (LLM)",
                "description": "Extract head|verb|tail triples from CoNLL-U.",
            },
        )

    rel_ver = load_agent("cid_re_verify")
    if rel_ver:
        put(
            "relation_verify_llm",
            {
                **rel_ver,
                **base_meta("relation", "llm", relation_mode="verify"),
                "name": "Relation Verification (LLM)",
                "description": "Verify a head–tail pair; output $ (positive) or ~ (negative) only.",
            },
        )

    rel_pair = load_agent("re_verify_pair_builder")
    if rel_pair:
        put(
            "relation_verify_to_pair",
            {
                **rel_pair,
                **base_meta("relation", "pgm", relation_mode="verify"),
                "name": "Relation Verify → Entity Pair",
                "description": "Map positive verification ($) to linked entity pair for evaluation.",
            },
        )

    dti = load_agent("dti_analyzer")
    if dti:
        put(
            "relation_dti_analyze",
            {
                **dti,
                **base_meta("relation", "llm", relation_mode="extract", tags=["dti"]),
                "name": "Drug–Target Interaction Analysis (LLM)",
                "description": "Analyze drug–target pairs (mechanism, affinity, binding).",
            },
        )

    # --- ontology ---
    for old, new, name, desc in [
        (
            "synonym_extraction",
            "ontology_synonym_extract",
            "Synonym Extraction (LLM)",
            "Extract synonym pairs as original|is|synonym lines.",
        ),
        (
            "cid_synonym_resolve",
            "ontology_synonym_resolve",
            "Synonym Resolution (LLM)",
            "LLM-based synonym merging for Chemical/Disease entities.",
        ),
        (
            "hypernym_identification",
            "ontology_hypernym_identify",
            "Hypernym Identification (LLM)",
            "Identify same-type hypernyms using ontology-style reasoning.",
        ),
        (
            "cid_hypernym_filter",
            "ontology_hypernym_filter",
            "Hypernym Filter (LLM)",
            "LLM-based filtering of generic hypernym entities.",
        ),
    ]:
        src = load_agent(old)
        if src:
            eng = "llm" if src.get("type") == "LLM" else "pgm"
            put(
                new,
                {
                    **src,
                    **base_meta("ontology", eng),
                    "name": name,
                    "description": desc,
                },
            )

    ent_link = load_agent("kg_entity_linker")
    if ent_link:
        put(
            "ontology_entity_link",
            {
                **ent_link,
                **base_meta("ontology", "llm"),
                "name": "Entity Linking / Normalization (LLM)",
                "description": "Normalize entity mentions to canonical surface forms for KG nodes.",
            },
        )

    # --- kg ---
    for old, new, name, desc in [
        (
            "kg_triple_extractor",
            "kg_triple_extract_llm",
            "Triple Extraction (LLM)",
            "Extract subject|predicate|object triples from text and entities.",
        ),
        (
            "kg_triple_merger",
            "kg_triple_merge",
            "Triple Merge (PGM)",
            "Deduplicate and merge relation lines with entity link map.",
        ),
        (
            "kg_rdf_export",
            "kg_rdf_export",
            "RDF-JSON Export (PGM)",
            "Export triples as JSON-LD-style nodes and edges.",
        ),
        (
            "bt_persistence",
            "kg_triple_persist",
            "Triple CSV Persistence (PGM)",
            "Persist head–verb–tail triples to CSV.",
        ),
    ]:
        src = load_agent(old)
        if src:
            eng = "llm" if src.get("type") == "LLM" else "pgm"
            put(
                new,
                {
                    **src,
                    **base_meta("kg", eng),
                    "name": name,
                    "description": desc,
                },
            )

    # --- evaluate ---
    for old, new, name, desc in [
        (
            "metrics",
            "eval_metrics",
            "Evaluation Metrics (PGM)",
            "Generic precision/recall/F1 for entity or relation sets.",
        ),
        (
            "word_seg_metrics",
            "eval_metrics_segment",
            "Segmentation Metrics (PGM)",
            "Boundary-level P/R/F1 for tokenized text.",
        ),
        (
            "cid_metrics",
            "eval_metrics_relation",
            "Relation Set Metrics (PGM)",
            "Precision/recall/F1 for relation pair sets.",
        ),
        (
            "create_evaluation_pairs",
            "eval_pair_generate",
            "Evaluation Pair Generator (PGM)",
            "Build head×tail candidate pairs for relation verification eval.",
        ),
    ]:
        src = load_agent(old)
        if src:
            put(
                new,
                {
                    **src,
                    **base_meta("evaluate", "pgm"),
                    "name": name,
                    "description": desc,
                },
            )

    # --- report ---
    for old, new, name, desc in [
        (
            "make_report",
            "report_experiment",
            "Experiment Report (LLM)",
            "Generate Markdown tables and analysis from experiment results.",
        ),
        (
            "format_json",
            "report_format_json",
            "Result Formatter (PGM)",
            "Package text, summary, and metadata into a result dict.",
        ),
    ]:
        src = load_agent(old)
        if src:
            eng = "llm" if src.get("type") == "LLM" else "pgm"
            put(
                new,
                {
                    **src,
                    **base_meta("report", eng),
                    "name": name,
                    "description": desc,
                },
            )

    return out


def replace_refs(obj, mapping: dict[str, str]):
    """Recursively replace agent ids in JSON structures."""
    if isinstance(obj, str):
        s = obj
        for old, new in sorted(mapping.items(), key=lambda x: -len(x[0])):
            s = re.sub(rf"\b{re.escape(old)}\b", new, s)
        return s
    if isinstance(obj, list):
        return [replace_refs(x, mapping) for x in obj]
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            nk = mapping.get(k, k) if isinstance(k, str) else k
            new_d[nk] = replace_refs(v, mapping)
        return new_d
    return obj


def main():
    agents = build_agents()
    missing = TARGET_IDS - set(agents.keys())
    if missing:
        raise SystemExit(f"Missing built agents: {missing}")

    # Remove all json files first
    for p in list(AGENTS.glob("*.json")):
        p.unlink()

    for aid, cfg in sorted(agents.items()):
        path = AGENTS / f"{aid}.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"write {aid}")

    # Update graphs
    full_map = {**RENAME}
    # identity for kg_rdf_export
    full_map["kg_rdf_export"] = "kg_rdf_export"

    for gp in GRAPHS.glob("*.json"):
        data = json.loads(gp.read_text(encoding="utf-8"))
        data = replace_refs(data, full_map)
        gp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"graph {gp.name}")

    print(f"Done: {len(agents)} agents")


if __name__ == "__main__":
    main()
