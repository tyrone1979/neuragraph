"""Sample inputs for every meta agent; writes tests/<agent_id>/sample.csv."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = ROOT / "tests"

TEXT = (
    "Aspirin may reduce the risk of heart disease. "
    "Lithium carbonate toxicity was reported in a newborn infant."
)
SENTENCE = "Aspirin may reduce the risk of heart disease."
LABELS = "Chemical,Disease"
ENTITIES = [
    {"text": "Aspirin", "id": "D001241", "label": "Chemical"},
    {"text": "heart disease", "id": "D006331", "label": "Disease"},
    {"text": "Lithium carbonate", "id": "D016651", "label": "Chemical"},
    {"text": "toxicity", "id": "D064420", "label": "Disease"},
]
ENTITY_LINK = {"Aspirin": "D001241", "heart disease": "D006331"}
PREDICTED_NER = {"Chemical": ["Aspirin"], "Disease": ["heart disease"]}
EXPECTED_NER = {"Chemical": ["Aspirin"], "Disease": ["heart disease", "pain"]}
RELATIONS = ["D001241 | D006331"]
GROUND_TRUTH = ["D001241 | D006331"]
METRICS_FLair = {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}}
METRICS_LLM = {"micro": {"precision": 0.9, "recall": 0.6, "f1": 0.72}}
MERGED_METRICS = {"flair": METRICS_FLair, "llm": METRICS_LLM}
TRIPLES = [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}]
RELATION_LINES = ["Aspirin | treats | heart disease"]
TREE = (
    "1\tAspirin\taspirin\tNN\t_\t2\tnsubj\t_\t_\t_\t_\n"
    "2\ttreats\ttreat\tVBZ\t_\t0\troot\t_\t_\t_\t_\n"
    "3\tpain\tpain\tNN\t_\t2\tobj\t_\t_\t_\t_\n"
)
SYNONYM_TEXT = (
    "Aspirin (acetylsalicylic acid) may reduce the risk of heart disease."
)
SEG_PRED = "| Aspirin | may | reduce |"
SEG_EXP = "| Aspirin | may | reduce |"
EXPERIMENT_PACKAGE = json.dumps(
    {
        "experiment": {"exp_id": "test-exp", "runner_id": "wf_cid_re_llm_linear"},
        "agents": [{"id": "relation_verify_llm", "type": "LLM"}],
        "states": [{"metrics": {"micro_f1": 0.5}}],
        "agent_versions": {"effective": {"relation_verify_llm": "current"}},
    },
    ensure_ascii=False,
)
DEV_TXT = ROOT / "comparison" / "data" / "CDR" / "dev.txt"
CHEMDISGENE_ENTITIES_RAW = "Chemical|Aspirin\nDisease|heart disease\nGene|PDE10A"
CHEMDISGENE_ENTITIES = {
    "Chemical": ["Aspirin"],
    "Disease": ["heart disease"],
    "Gene": ["PDE10A"],
}
_CHEMDISGENE_RE_ROW = {"text": TEXT, "head": "Aspirin", "tail": "heart disease"}
_CHEMDISGENE_RE_ENTITY_TYPE_ROW = {
    "text": SYNONYM_TEXT,
    "head": "Aspirin",
    "tail": "acetylsalicylic acid",
    "entity_type": "Chemical",
}

# agent_id -> one CSV row (values may be str, list, dict — serialized on write)
AGENT_SAMPLE_ROWS: dict[str, dict[str, Any]] = {
    "agent_refiner": {"text": EXPERIMENT_PACKAGE},
    "cid_pair_generate": {"filtered_entities": ENTITIES},
    "dataset_cid_tuning_build": {
        "agent_id": "wf_cid_re_llm_linear",
        "runner_id": "wf_cid_re_llm_linear",
        "format": "re",
        "source": "comparison/data/CDR/dev.txt",
        "size": "2",
        "tuning_out": "cid_agent_test_tuning.csv",
        "test_out": "cid_agent_test_test.csv",
        "write_test_remain": "false",
        "mirror_agent_id": "",
        "mirror_format": "ner",
    },
    "dataset_chemdisgene_build": {
        "agent_id": "wf_chemdisgene_re_llm_linear",
        "runner_id": "wf_chemdisgene_re_llm_linear",
        "format": "re",
        "source": "data/raw/chemdisgene.txt",
        "output_name": "chemdisgene_agent_test.csv",
        "mirror_agent_id": "ner_chemdisgene_llm",
        "mirror_format": "ner",
    },
    "chemdisgene_answer_map": {
        "result": "11",
        "rel_template": "chem_disease:affects",
        "head": "Aspirin",
        "tail": "heart disease",
    },
    "chemdisgene_ner_parse": {
        "entities_raw": CHEMDISGENE_ENTITIES_RAW,
        "text": TEXT,
    },
    "chemdisgene_pair_generate": {
        "entities": CHEMDISGENE_ENTITIES,
        "text": TEXT,
    },
    "chemdisgene_result_to_relation": {
        "rel_types": ["chem_disease:therapeutic"],
        "head": "Aspirin",
        "tail": "heart disease",
    },
    "chemdisgene_re_synonym": dict(_CHEMDISGENE_RE_ENTITY_TYPE_ROW),
    "chemdisgene_re_hypernyms": dict(_CHEMDISGENE_RE_ENTITY_TYPE_ROW),
    "ner_chemdisgene_llm": {"text": TEXT},
    "cid_entities_dedupe_mesh": {"entities": ENTITIES},
    "ner_entities_to_re_format": {"entities": PREDICTED_NER},
    "e2e_hypernym_filter": {"entities": ENTITIES, "text": TEXT},
    "e2e_synonym_filter": {"entities": ENTITIES, "text": TEXT},
    "e2e_entities_dedup_by_id": {"entities": ENTITIES},
    "e2e_entities_passthrough": {"entities": ENTITIES},
    "e2e_entities_assign_group_ids": {
        "entities": ENTITIES,
        "filtered_entities": ENTITIES,
    },
    "e2e_entity_aliases_snapshot": {"filtered_entities": ENTITIES},
    "eval_flair": {"flair_entities": PREDICTED_NER},
    "eval_llm": {"entities": PREDICTED_NER},
    "eval_metrics": {"predicted": PREDICTED_NER, "expected": EXPECTED_NER},
    "eval_metrics_relation": {
        "relations": ["Aspirin | CID | heart disease"],
        "ground_truth": [
            "Aspirin | CID | heart disease",
            "Lithium carbonate | CID | toxicity",
        ],
        "entities": ENTITIES,
    },
    "eval_metrics_segment": {"predicted": SEG_PRED, "expected": SEG_EXP},
    "eval_pair_generate": {"expected_entities": PREDICTED_NER},
    "kg_rdf_export": {"triples": TRIPLES},
    "kg_triple_extract_llm": {"text": SENTENCE, "entities": PREDICTED_NER},
    "kg_triple_merge": {"relations": RELATION_LINES, "entity_link": ENTITY_LINK},
    "kg_triple_persist": {
        "doc_id": "agent_test_doc",
        "triples": TRIPLES,
        "synonyms": {"Aspirin": ["acetylsalicylic acid"]},
    },
    "merge_metrics": {"flair_metrics": METRICS_FLair, "llm_metrics": METRICS_LLM},
    "ner_comparison_report": {"merged_metrics": MERGED_METRICS, "text": TEXT},
    "ner_flair_aggregate": {
        "sentences": [SENTENCE],
        "predicted": [PREDICTED_NER],
        "ner_flair_sent": PREDICTED_NER,
    },
    "ner_flair_doc": {"text": TEXT, "labels": LABELS},
    "ner_flair_sent": {"sentence": SENTENCE, "labels": LABELS},
    "ner_from_tree_llm": {"tree": TREE, "labels": LABELS},
    "ner_llm": {"text": SENTENCE, "labels": LABELS},
    "ontology_entity_link": {"entities": PREDICTED_NER},
    "ontology_hypernym_filter": {"entities": ENTITIES},
    "ontology_synonym_resolve": {"text": SENTENCE, "entities": PREDICTED_NER},
    "relation_extract_llm": {"text": SENTENCE, "entities": PREDICTED_NER},
    "relation_extract_pubtator": {
        "text": SENTENCE,
        "entities": ENTITIES[:2],
        "pmid": "12345678",
    },
    "relation_from_tree_llm": {"tree": TREE},
    "relation_result_to_id_pair": {
        "result": "$",
        "head_id": "D001241",
        "tail_id": "D006331",
        "text": "Aspirin treats heart disease.",
        "head": "Aspirin",
        "tail": "heart disease",
    },
    "relation_verify_llm": {"text": SENTENCE, "head": "Aspirin", "tail": "heart disease"},
    "relation_verify_to_pair": {
        "result": "$",
        "head": "Aspirin",
        "tail": "heart disease",
        "entity_link": ENTITY_LINK,
    },
    "report_comparator": {"text": EXPERIMENT_PACKAGE},
    "report_experiment": {"text": EXPERIMENT_PACKAGE},
    "report_experiment_tool": {"text": EXPERIMENT_PACKAGE},
    "report_format_json": {"text": TEXT, "summary": "Aspirin may reduce heart disease risk."},
    "syntax_dep_parse": {"sentence": SENTENCE},
    "text_coreference": {"text": TEXT},
    "text_sentence_split": {"text": TEXT},
    "text_summarize": {"text": TEXT},
    "text_word_segment": {"text": "Aspirin may reduce heart disease risk."},
    "llm_link_bulk_update": {
        "target_model": "deepseek",
        "source_model": "",
        "dry_run": "true",
        "agent_ids": "",
        "change_note": "agent test dry run",
    },
}

_CHEMDISGENE_RE_AGENTS = (
    "chemdisgene_re_chem_disease_affects",
    "chemdisgene_re_chem_gene_activity",
    "chemdisgene_re_chem_gene_aff_bind",
    "chemdisgene_re_chem_gene_aff_expr",
    "chemdisgene_re_chem_gene_aff_local",
    "chemdisgene_re_chem_gene_dec_metab",
    "chemdisgene_re_chem_gene_expression",
    "chemdisgene_re_chem_gene_inc_activity",
    "chemdisgene_re_chem_gene_inc_metab",
    "chemdisgene_re_chem_gene_transport",
    "chemdisgene_re_gene_disease_marker",
    "chemdisgene_re_gene_disease_therapeutic",
)
for _agent_id in _CHEMDISGENE_RE_AGENTS:
    AGENT_SAMPLE_ROWS[_agent_id] = dict(_CHEMDISGENE_RE_ROW)


def _cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_agent_sample_csv(agent_id: str, row: dict[str, Any] | None = None) -> Path:
    row = row or AGENT_SAMPLE_ROWS[agent_id]
    agent_dir = TESTS_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "sample.csv"
    fieldnames = list(row.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({k: _cell(row[k]) for k in fieldnames})
    return path


def write_all_agent_sample_csvs() -> list[str]:
    from service.meta.loader import MetaLoader

    agents_dir = ROOT / "meta" / "agents"
    written: list[str] = []
    for path in sorted(agents_dir.glob("*.json")):
        agent_id = path.stem
        if agent_id not in AGENT_SAMPLE_ROWS:
            raise KeyError(f"Missing fixture row for agent {agent_id}")
        meta = MetaLoader.load("agents", agent_id) or {}
        row = AGENT_SAMPLE_ROWS[agent_id]
        for key in meta.get("inputs") or []:
            if key not in row:
                raise KeyError(f"Fixture for {agent_id} missing required input {key!r}")
        write_agent_sample_csv(agent_id, row)
        written.append(agent_id)
    return written
