# NeuraGraph: A lightweight platform for building LLM-powered agent workflows specialized in NLP and Knowledge Graph tasks

Paper link: [comming soon]

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Early Development](https://img.shields.io/badge/status-early%20development-orange)](https://github.com/tyrone1979/neuragraph)

## Abstract

Focus: Biomedical text mining pipelines (NER, Relation Extraction, Coreference Resolution, Synonym/Hypernym extraction, Dependency Parsing → Triple conversion, etc.)  
Drag-and-drop LLM + rule-based + Flair components into reusable workflows to extract structured knowledge (entities, relations, triples) from biomedical abstracts—with experiment tracking, metric comparison, and persistence.

## Key Use Cases

- Sentence-level / document-level **Named Entity Recognition** (e.g., Chemical, Disease) and **Relation Extraction** (e.g., Chemical–Disease links)
- Sentence splitting and medical-specific word segmentation
- Synonym & hypernym detection in biomedical context (using MeSH codes)
- Coreference resolution for cleaner entity linking
- Dependency parse tree analysis (CoNLL-U output via LLM)
- Side-by-side comparison of LLM vs. Flair vs. rule-based pipelines
- Metrics calculation (precision/recall/F1) + error analysis
- Auto-generated reports (Markdown tables + conclusions)
- Persistence of triples/entities to CSV for downstream KG building
- ... (expand as you hack more)

## Tech Stack Highlights

- **Backend**: Flask + Python 3.12+
- **Frontend**: Bootstrap 5 + JointJS (interactive graph editor)
- **Workflow Engine**: Custom lightweight DAG (START → nodes/subgraphs → END; future: langgraph migration?)
- **LLM Integration**: OpenAI, Ollama, custom endpoints, …
- **Experiment & Data**:
  - SSE streaming progress + final Markdown reports
  - CSV/TXT/JSON data file support
- **Persistence**: JSON metadata + results (PostgreSQL optional for workflow state)


## Quick Start

### Software Requirements
- OS: Ubuntu 24.04.6 LTS (GNU/Linux 5.4.0-205-generic x86_64) tested
- Python: 3.12.3 or 3.11.11 tested
- Optional: PostgreSQL (for state persistence), Ollama (local LLM)
- **Flair / HunFlair2** (recommended for biomedical NER): install `flair` and place the model under `models/hunflair2-ner/` (first startup loads the tagger and may take longer)

### Setup
```bash
# Clone if you haven't
git clone https://github.com/tyrone1979/neuragraph.git  # assuming this is your repo
cd neuragraph

# Virtualenv (highly recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install deps
pip install -r requirements.txt
```

### Run
```bash
python run.sh
# or python app.py
```

### Open Browser
Hit http://127.0.0.1:5001  
![homepage.png](doc/images/homepage.png)

### First 5-Minute Tour
- **LLMs** tab → Add at least one LLM config (Ollama recommended for quick start)
- **Agents** → Browse agents by `layer` (e.g., `text_sentence_split`, `ner_llm`, `relation_extract_llm`)
- **Workflows** → Open an example graph (e.g., `wf_doc_ner_llm_eval`)
- **Datasets** → Upload a small test set (abstracts + optional gold NER/RE)
- **Experiments** → Pick a graph + dataset → Run → Watch streaming output & report

### Guidelines and Manual
- [CODE_GUIDELINES.md](doc/CODE_GUIDELINES.md) – For hacking on the code
- [MANUAL.md](doc/MANUAL.md) – Step-by-step ops guide with screenshots

## Agent Catalog

Agents: `meta/agents/<id>.json` — each file includes **`layer`**, **`engine`**, **`name`**, **`description`**.  
Domain-specific behaviour is configured via **`labels`**, **`entity_types`**, prompts — not via `cid_` / `biomed_` prefixes.

### `layer=document` · `engine=llm`

| ID | Name |
|----|------|
| `text_sentence_split` | Sentence Split |
| `text_word_segment` | Word Segmentation |
| `text_coreference` | Coreference Resolution |
| `text_summarize` | Text Summarization |

### `layer=syntax` · `engine=llm`

| ID | Name |
|----|------|
| `syntax_dep_parse` | Dependency Parse (CoNLL-U) |

### `layer=ner`

| ID | engine | granularity | Name |
|----|--------|-------------|------|
| `ner_llm` | llm | document | NER (LLM, configurable `{labels}`) |
| `ner_flair_sent` | flair | sentence | NER (Flair, sentence) |
| `ner_flair_doc` | flair | document | NER (Flair, document) |
| `ner_from_tree_llm` | llm | sentence | NER from Dependency Tree |

### `layer=relation`

| ID | engine | mode | Name |
|----|--------|------|------|
| `relation_extract_llm` | llm | extract | Relation Extraction (text + entities) |
| `relation_from_tree_llm` | llm | from_tree | Relation Extraction from CoNLL-U |
| `relation_verify_llm` | llm | verify | Relation Verification ($ / ~) |
| `relation_verify_to_pair` | pgm | verify | Verify → entity pair |
| `relation_dti_analyze` | llm | extract | Drug–Target Interaction (`tags: dti`) |

### `layer=ontology`

| ID | engine | Name |
|----|--------|------|
| `ontology_synonym_extract` | llm | Synonym Extraction |
| `ontology_synonym_resolve` | pgm | Synonym Resolution |
| `ontology_hypernym_identify` | llm | Hypernym Identification |
| `ontology_hypernym_filter` | pgm | Hypernym Filter |
| `ontology_entity_link` | llm | Entity Linking / Normalization |

### `layer=kg`

| ID | engine | Name |
|----|--------|------|
| `kg_triple_extract_llm` | llm | Triple Extraction |
| `kg_triple_merge` | pgm | Triple Merge |
| `kg_rdf_export` | pgm | RDF-JSON Export |
| `kg_triple_persist` | pgm | Triple CSV Persistence |

### `layer=evaluate` · `engine=pgm`

| ID | Name |
|----|------|
| `eval_metrics` | Generic P/R/F1 |
| `eval_metrics_segment` | Segmentation boundaries |
| `eval_metrics_relation` | Relation set metrics |
| `eval_pair_generate` | Head×tail pair generator |

### `layer=report`

| ID | engine | Name |
|----|--------|------|
| `report_experiment` | llm | Experiment Markdown report |
| `report_format_json` | pgm | Result JSON formatter |

**Migration script:** `scripts/migrate_agents_taxonomy.py` (re-run only on a clean backup).

### Example Workflows (`meta/graphs/wf_*.json`)

| Graph ID | dataset | task | flow_pattern |
|----------|---------|------|--------------|
| `wf_doc_re_nested_branch` | doc_re | re | **branch + nested loop** (4 branches) |
| `wf_doc_ner_loop_branch` | doc_ner | ner | **loop + branch** (4 branches) |
| `wf_cid_re_branch` | cid | re | **branch** (4 branches) |
| `wf_re_verify_llm_loop` | re_verify | re_verify | **loop** |
| `wf_kg_syntax_loop` | kg_triple | kg | **loop** |
| `wf_cid_ner_llm_eval` | cid | ner | linear |
| `wf_cid_ner_flair_eval` | cid | ner | linear |
| `wf_doc_ner_llm_eval` | doc_ner | ner | linear |
| `wf_doc_ner_flair_eval` | doc_ner | ner | linear |
| `wf_cid_re_llm_linear` | cid | re | linear |
| `wf_kg_llm_full` | kg | kg | linear |
| `wf_kg_flair_full` | kg | kg | linear |
| `wf_word_seg_llm_eval` | word_seg | segment | linear |
| `wf_general_report_linear` | general | report | linear |

Subgraphs (`sg_*`) are loop/branch bodies — not used as Experiment runners directly.

Migration: `scripts/migrate_graphs_taxonomy.py`

## Roadmap (as of Jan 22, 2026 – HK time, yo!)
- [x] Visual graph editor & basic execution
- [x] LLM/Flair integration for BioNLP primitives
- [x] Experiment runner with SSE & reports
- [ ] Multiple dataset format supports.
- [x] Agent catalog cleanup + biomedical KG agents (Flair + LLM)


## Citation
```
@misc{neuragraph2026,
  author = {Lei Zhao},
  title = {NeuraGraph:A Lightweight Platform for Building LLM-Powered Agent Workflows Specialized in Biomedical NLP and Knowledge Graph Tasks },
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/tyrone1979/neuragraph}}
}
```
