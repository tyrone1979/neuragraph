# NeuraGraph: A lightweight platform for building LLM-powered agent workflows specialized in NLP and Knowledge Graph tasks

Paper link: [comming soon]

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
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

- **Backend**: Flask + Python 3.11+
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
- Optional: PostgreSQL (for state persistence), Ollama (local LLM), Flair (BioNER)

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
- **Agents** → Browse existing agents (e.g., sentence_split, dependency_parse, bio_ner, relation_extraction)
- **Workflows** → Open an example graph (e.g., ner_4_doc_llm.json)
- **Datasets** → Upload a small test set (abstracts + optional gold NER/RE)
- **Experiments** → Pick a graph + dataset → Run → Watch streaming output & report

### Guidelines and Manual
- [CODE_GUIDELINES.md](doc/CODE_GUIDELINES.md) – For hacking on the code
- [MANUAL.md](doc/MANUAL.md) – Step-by-step ops guide with screenshots

## Roadmap (as of Jan 22, 2026 – HK time, yo!)
- [x] Visual graph editor & basic execution
- [x] LLM/Flair integration for BioNLP primitives
- [x] Experiment runner with SSE & reports
- [ ] Multiple dataset format supports.


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
