"""One-off: add description and normalize agent names from catalog."""
import json
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent.parent / "meta" / "agents"

CATALOG = {
    "bio_ner": {
        "name": "Biomedical Flair NER (Sentence)",
        "description": "HunFlair2 sentence-level tagging via Flair plugin; outputs label→mention lists.",
    },
    "biomed_ner": {
        "name": "Biomedical LLM NER",
        "description": "LLM extraction of Chemical and Disease entities as JSON (used in biomed RE workflow).",
    },
    "biomed_re_branch": {
        "name": "RE Branch Gate",
        "description": "Passthrough PGM for graph branch flow node; routing is configured in workflow flowNodes.",
    },
    "biomed_relation_extract": {
        "name": "Biomedical LLM Relation Extraction",
        "description": "Extract chemical–disease / treatment relations using text and NER context.",
    },
    "bt_persistence": {
        "name": "KG Triple CSV Persistence",
        "description": "Persist head–verb–tail triples and synonyms to CSV under result/.",
    },
    "cid_hypernym_filter": {
        "name": "CID Hypernym Filter",
        "description": "Remove overly generic hypernym terms from CID entity lists before RE.",
    },
    "cid_metrics": {
        "name": "CID Relation Metrics",
        "description": "Precision/recall/F1 for chemical–induced–disease relation sets.",
    },
    "cid_ner": {
        "name": "CID Pipeline NER",
        "description": "Structured Chemical/Disease extraction with spans for CID evaluation.",
    },
    "cid_re": {
        "name": "CID Relation Extraction",
        "description": "Extract chemical-induces-disease causal relations for CID tasks.",
    },
    "cid_re_verify": {
        "name": "CID Relation Verification",
        "description": "Binary LLM verifier: output $ (positive) or ~ (negative) for a head–tail pair.",
    },
    "cid_synonym_resolve": {
        "name": "CID Synonym Resolver",
        "description": "Merge synonym entity mentions to canonical forms in CID pipeline.",
    },
    "coreference_resolution": {
        "name": "Biomedical Coreference Resolution",
        "description": "Resolve pronouns in abstracts to improve entity/relation clarity.",
    },
    "create_evaluation_pairs": {
        "name": "Evaluation Pair Generator",
        "description": "Cartesian product of Chemical × Disease entities for relation verification eval.",
    },
    "dependency_parse": {
        "name": "Dependency Parser (CoNLL-U)",
        "description": "LLM converts an English sentence to CoNLL-U for syntax-based extraction.",
    },
    "dti_analyzer": {
        "name": "Drug–Target Interaction Analyzer",
        "description": "LLM analysis of drug chemistry and protein target (mechanism, affinity, binding).",
    },
    "entity_extract": {
        "name": "Tree-based Entity Extraction",
        "description": "NER from a CoNLL-U dependency tree for given entity types.",
    },
    "format_json": {
        "name": "Result JSON Formatter",
        "description": "Package text, summary, and lengths into a single result dict.",
    },
    "gene_protein_ner": {
        "name": "Gene & Protein NER",
        "description": "LLM extraction of gene and protein mentions from biomedical text.",
    },
    "hypernym_identification": {
        "name": "Hypernym Identification (MeSH)",
        "description": "Find same-type biomedical hypernyms using MeSH-style reasoning.",
    },
    "make_report": {
        "name": "Experiment Report Generator",
        "description": "Turn experiment metrics/results into a Markdown analysis report.",
    },
    "metrics": {
        "name": "Generic Metrics Calculator",
        "description": "Precision/recall/F1 via MetricsCalculation plugin (dict or pair lists).",
    },
    "ner_extractor": {
        "name": "Configurable LLM NER",
        "description": "Generic biomedical NER with user-specified entity type labels.",
    },
    "ner_with_tool": {
        "name": "LLM NER with Flair Tool",
        "description": "Split document, call Flair NER tool per sentence, aggregate Chemical/Disease.",
    },
    "relation_extraction": {
        "name": "Dependency-tree Relation Extraction",
        "description": "Extract head|verb|tail triples from CoNLL-U trees.",
    },
    "sentence_split": {
        "name": "Biomedical Sentence Splitter",
        "description": "Split abstracts into a JSON array of sentences.",
    },
    "sub_ner": {
        "name": "Sentence Loop (Flair NER)",
        "description": "SUB agent: iterate sentences and run Flair NER subgraph per sentence.",
    },
    "sub_ner_llm": {
        "name": "Sentence Loop (LLM NER)",
        "description": "SUB agent: iterate sentences for LLM/tree-based NER subgraph.",
    },
    "sub_re": {
        "name": "Sentence Loop (Relation Extraction)",
        "description": "SUB agent: per-sentence relation/triple extraction.",
    },
    "sub_rv": {
        "name": "Pair Loop (Relation Verification)",
        "description": "SUB agent: iterate head–tail pairs for CID relation verification.",
    },
    "summarize_text": {
        "name": "Biomedical Text Summarizer",
        "description": "Short 2–3 sentence summary of biomedical text.",
    },
    "synonym_extraction": {
        "name": "Synonym Pair Extraction",
        "description": "Extract original|is|synonym lines from abstracts for KG lexicon building.",
    },
    "word_segmentation": {
        "name": "Medical Word Segmentation",
        "description": "Symbol-aware tokenization with | delimiters for Chinese/English clinical text.",
    },
    "word_seg_metrics": {
        "name": "Word Segmentation Metrics",
        "description": "Boundary-level P/R/F1 and error analysis for segmented text.",
    },
}

SKIP = {
    "re_verify_pair_builder",
    "kg_triple_extractor",
    "kg_entity_linker",
    "kg_triple_merger",
    "biomed_flair_doc_ner",
    "kg_rdf_export",
}


def main():
    for path in sorted(AGENTS_DIR.glob("*.json")):
        aid = path.stem
        if aid in SKIP:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = CATALOG.get(aid)
        if not meta:
            print(f"skip (no catalog): {aid}")
            continue
        data["name"] = meta["name"]
        data["description"] = meta["description"]
        if aid == "biomed_ner":
            data.pop("conditions", None)
            data.pop("loopConfig", None)
        if aid == "bt_persistence" and not data.get("process"):
            data["process"] = "__result__ = state.get('triples') or []"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {aid}")


if __name__ == "__main__":
    main()
