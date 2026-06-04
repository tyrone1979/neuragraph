"""Generate §4 inventory tables (S14–S19) with row numbers and full descriptions."""
import json
import re
import sys
from pathlib import Path

PGM_DESCRIPTIONS = {
    "cid_pair_generate": "Builds chemical–disease head/tail text pairs with MeSH IDs from filtered Chemical and Disease entities.",
    "dataset_cid_tuning_build": "Builds CID relation tuning and test splits from a PubTator source file via the CidDatasetBuilder plugin.",
    "eval_flair": "Counts unique FLAIR NER entities per label and returns total and per-label entity counts.",
    "eval_llm": "Counts unique LLM NER entities per label and returns total and per-label entity counts.",
    "eval_metrics": "Computes NER precision, recall, and F1 by comparing predicted and expected entity sets via MetricsCalculation.",
    "eval_metrics_relation": "Evaluates chemical–induced-disease relation sets by normalizing and comparing predicted relations to ground truth.",
    "eval_metrics_segment": "Scores pipe-delimited word segmentation by boundary precision, recall, F1, and segmentation error analysis.",
    "eval_pair_generate": "Generates all chemical–disease evaluation pairs from expected Chemical and Disease entity lists.",
    "kg_rdf_export": "Exports knowledge-graph triples to RDF-JSON with node labels and subject–predicate–object edges.",
    "kg_triple_merge": "Merges pipe-delimited relations with entity-link canonicalization and deduplicates head–predicate–tail triples.",
    "kg_triple_persist": "Persists merged knowledge-graph triples to CSV under result with head, verb, and tail columns.",
    "llm_link_bulk_update": "Bulk-updates LLM connector links on selected agents from a source model to a target, optionally dry-run.",
    "merge_metrics": "Combines FLAIR and LLM NER metric dictionaries into a single merged_metrics report object.",
    "ner_flair_aggregate": "Aggregates per-sentence FLAIR NER outputs into document-level label-to-unique-entity-text dictionaries.",
    "ner_flair_doc": "Runs HunFlair2 NER on a document split into sentences and returns deduplicated entities per label.",
    "ner_flair_sent": "Tags one sentence with HunFlair2 NER and returns predicted entity texts grouped by label.",
    "ontology_mesh_lookup": "Looks up MeSH descriptors for a query and returns mesh IDs, synonyms, and hypernyms per match.",
    "relation_extract_pubtator": "Extracts chemical–disease relations from text or PMID using PubTator3 and local entity annotations.",
    "relation_result_to_id_pair": "Emits head_id|tail_id CID relation lines when verification is positive, with negation and weak-association guards.",
    "relation_verify_to_pair": "Maps a positive relation verification to canonical head and tail entity IDs from entity_link.",
    "report_format_json": "Formats original text and summary into JSON with character lengths for reporting pipelines.",
}

# Reference workflows shipped in v2.x (excludes _opt_* copies and eval-only variants).
WF_EXCLUDE = {"wf_cid_ner_flair_eval"}

PARSER_ROWS = [
    (
        "parser_cdr",
        "CDR (PubTator)",
        "Load BioCreative V CDR PubTator .txt articles with gold entities and CID relations (CIDParser).",
    ),
    (
        "parser_chemdisgene",
        "ChemDisGene",
        "Load ChemDisGene article .txt files with companion .tsv annotation trees (ChemDisGeneParser).",
    ),
    (
        "parser_plain_text",
        "Plain text (raw upload)",
        "Load user-uploaded plain-text .txt from data/raw for batch runs without bundled gold files.",
    ),
]


def esc(s: str) -> str:
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    s = s.replace("$", "induces").replace("~", "does not induce")
    s = re.sub(r"if induce \(\$\)\.", "if verdict is induces.", s, flags=re.I)
    s = re.sub(r"if induce \(induces\)\.", "if verdict is induces.", s, flags=re.I)
    s = re.sub(r"output id \| id", "output MeSH id pair", s, flags=re.I)
    s = re.sub(r"output id / id", "output MeSH id pair", s, flags=re.I)
    return s or "—"


def desc_agent(stem: str, d: dict) -> str:
    if d.get("description"):
        return str(d["description"])
    pt = d.get("prompt_template") or {}
    if isinstance(pt, dict) and pt.get("description"):
        return str(pt["description"])
    if d.get("type") == "PGM" and stem in PGM_DESCRIPTIONS:
        return PGM_DESCRIPTIONS[stem]
    return "—"


def md_table(rows: list, caption: str) -> str:
    lines = [f"**{caption}**", "", "| No. | ID | Name | Description |", "|---:|---|---|---|"]
    for i, (id_, name, desc) in enumerate(rows, 1):
        lines.append(f"| {i} | `{id_}` | {esc(name)} | {esc(desc)} |")
    return "\n".join(lines)


def write_pgm_meta() -> None:
    for stem, desc in PGM_DESCRIPTIONS.items():
        p = Path("meta/agents") / f"{stem}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("description") != desc:
            d["description"] = desc
            p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_graph_descriptions() -> None:
    fixes = {
        "sg_cid_re_verify": "Verify one Chemical–Disease pair; output MeSH id pair when verdict is induces.",
        "wf_flair_vs_llm_ner": "Sentence split, Flair loop NER, LLM NER, per-path metrics, and ner_comparison_report on the same document.",
    }
    for stem, desc in fixes.items():
        p = Path("meta/graphs") / f"{stem}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("description") != desc:
            d["description"] = desc
            p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if "--write-meta" in sys.argv:
        write_pgm_meta()
        patch_graph_descriptions()
        print("Updated PGM agent and graph descriptions in meta/")

    llm, pgm = [], []
    for p in sorted(Path("meta/agents").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        row = (p.stem, d.get("name", ""), desc_agent(p.stem, d))
        (llm if d.get("type") == "LLM" else pgm).append(row)

    sg, wf = [], []
    for p in sorted(Path("meta/graphs").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        stem = p.stem
        if stem.startswith("sg_"):
            sg.append((stem, d.get("name", ""), d.get("description", "")))
        elif stem.startswith("wf_") and "_opt_" not in stem and stem not in WF_EXCLUDE:
            wf.append((stem, d.get("name", ""), d.get("description", "")))

    tools = []
    for p in sorted(Path("meta/tools").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        tools.append((p.stem, d.get("name", ""), d.get("description", "")))

    sections = [
        "### 4.1 Agents (43)",
        "",
        md_table(llm, "Table S14. LLM agents (22)"),
        "",
        md_table(pgm, "Table S15. PGM agents (21)"),
        "",
        "### 4.2 Reusable subgraphs (7)",
        "",
        md_table(sg, "Table S16. Reusable subgraphs (7)"),
        "",
        "### 4.3 Reference workflows (17)",
        "",
        md_table(wf, "Table S17. Reference workflows (17)"),
        "",
        "### 4.4 Callable tools (12)",
        "",
        md_table(tools, "Table S18. Callable tools (12)"),
        "",
        "### 4.5 Native dataset parsers",
        "",
        md_table(PARSER_ROWS, "Table S19. Native dataset parsers (3)"),
        "",
        "Built-in loaders are selected automatically from dataset folder layout (`data/data_load.py`: PubTator .txt, ChemDisGene .tsv trees, or `data/raw` uploads).",
    ]
    Path(".cursor_tmp/sec4_body.md").write_text("\n".join(sections), encoding="utf-8")
    missing = [
        f"{t} {id_}"
        for t, rows in [("LLM", llm), ("PGM", pgm), ("sg", sg), ("wf", wf), ("tool", tools)]
        for id_, _, desc in rows
        if desc == "—"
    ]
    if missing:
        print("WARNING missing descriptions:", ", ".join(missing))
    else:
        print("All rows have descriptions.")


if __name__ == "__main__":
    main()
