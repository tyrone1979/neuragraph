# Supplementary Material

This file is the revised supplementary text for the NeuraGraph Application Note (v2.x). Sync into `supplementary_data.docx` for submission. Figure/table numbers use **S** prefix; keep existing figure files (Fig. S2–S4) where paths still match.

---

## 1. Software architecture

NeuraGraph adopts a three-layer architecture (Fig. 1). The **Presentation Layer** provides a browser-based visual editor for drag-and-drop workflow assembly with real-time **input-inference validation**. The **Service Layer** (Flask API, LangGraph orchestration, plugins, LLM connectors) runs batch workflows, optional **sandbox sidecars** for heavy local models, and an **experiment wizard** (test/tuning split, reporting, optimization). The **Persistence Layer** stores versioned agent/workflow JSON under `meta/`, per-experiment `states.json`, and Markdown reports under `result/`.

**Fig. 1.** High-level architecture: Presentation Layer (visual editor), Service Layer (API, LangGraph, plugins), Persistence Layer (metadata, results, reports).

**Distributed inventory (release v2.x).** 47 pre-built agents (21 LLM, 26 PGM), 9 reusable subgraphs (`sg_*`), 19 reference workflows (`wf_*`), 12 tools, native parsers for **CDR**, **ChemDisGene**, and plain text.

---

## 2. Core features implementation

### Feature 1 — Automatic input inference (Algorithm S1)

Given a directed workflow graph G=(V,E) where each node declares inputs and outputs, NeuraGraph computes the minimal set of **global inputs** required to execute G, ensuring every data dependency is satisfied before run-time (see Algorithm S1 table).

### Feature 2 — Recursive subgraph composition (Algorithm S2)

Hierarchical pipelines are built with `**flowNodes` of kind `loop`**, each referencing a reusable subgraph file `sg_*` (e.g. sentence-level NER, pairwise relation verification). For each element of a list in shared state (`sentences`, `pairs`, …), the engine runs the loop body once and **merges** list/dict outputs into the parent state. This replaces legacy SUB-type controllers in release 1.0. Algorithm S2 summarizes the invocation pattern.

### Feature 3 — Plugin integration and sandbox execution

Local biomedical models (e.g. Flair/HunFlair2) are integrated through a unified `Plugin` base class whose `load()` method exposes named capabilities to programmatic agents and tools. Heavy dependencies run in **isolated sandbox sidecars**—separate local processes with dedicated virtual environments (`meta/plugins_sandbox.json`, default Flair sidecar on port 5002)—invoked by the main orchestrator via HTTP (`/health`, `/pgm/run`, `/tool/run`). Lightweight agents execute **in-process** under import-restricted PGM execution. Plugins are cached after first load. Custom models can be added via `sandbox/<id>/plugins_impl.py` or the ≤50-line `sandbox/_template` without Docker.

### Feature 4 — Batch experiments and reproducibility

Each batch experiment persists workflow JSON (optional **fixed agent definitions** recorded in `agentVersions`), experiment metadata (`meta/exps/<id>.json`), and per-sample `**result/<exp_id>/states.json`** (inputs, per-node traces, predictions, metrics). Agent and tool definitions are archived on save (`meta/agent_versions/`, `meta/tool_versions/`) with content hashes so a past configuration can be reloaded; re-runs use the stored workflow and agent files rather than silently using the latest editable definitions (**configuration-level reproducibility**; LLM stochasticity depends on fixed model endpoints and sampling settings).

### Feature 5 — Evaluation metrics

When gold annotations are provided, NeuraGraph computes precision (P), recall (R), and F1 at **micro-** and **macro-average** levels. For each instance i:


P_i=\frac{TP_i}{TP_i+FP_i},\quad R_i=\frac{TP_i}{TP_i+FN_i},\quad F1_i=\frac{2P_iR_i}{P_i+R_i}.


**Micro-averaged** metrics aggregate counts over all instances before computing ratios; **macro-averaged** metrics average per-instance P_i, R_i, F1_i. Relation tasks use article-level aggregation where appropriate to avoid pseudoreplication from sentence-level counting.

### Feature 6 — LLM-powered reporting and tuning-driven refinement

A four-step **experiment wizard** (Fig. 1D) separates **test** and **tuning** datasets and links batch evaluation, LLM reporting, and tuning-guided workflow updates without manual orchestration coding.

1. **Configure.** Select a workflow (or single-agent runner), assign test and tuning CSV files from `tests/<runner_id>/` (or generate splits via stratified auto-split), and preview samples to confirm columns and gold fields.
2. **Baseline test and report.** Batch-run the workflow on the **test** split; persist per-sample `result/<exp_id>/states.json`. A reporting agent (`report_experiment` / `report_experiment_tool`) reads these artifacts and experiment metadata and writes a structured **Markdown** baseline report (micro/macro metric tables, FN/FP examples, suggested agent edits) using a configurable local or cloud LLM.
3. **Tuning and optimize.** Batch-run on the **tuning** split and generate a tuning-set diagnostic report. The wizard’s optimize step passes that report to `agent_refiner`, which returns structured per-agent modification plans (**biomedical semantic** prompt edits to the LLM verifier; PGM/process proximity guards are filtered out). For each plan, the platform applies the edit, re-runs the **tuning** split, and **keeps the round only when tuning macro-F1 increases**.
4. **Optimized test.** Re-run the selected workflow on the **test** split; the UI compares baseline versus optimized precision, recall, and F1 and can display an optimized test report.

Built-in **micro-** and **macro-averaged** metrics (Feature 5) are logged throughout; relation tasks use article-level aggregation where appropriate.

---

## 3. Illustrative examples

### 3.1 An end-to-end workflow for NER

**Dataset.** BioCreative V CDR corpus; NER evaluation uses the test split summarized in **Table S1**.

**Table S1.** Benchmark dataset (NER).


| Dataset | # Test articles | Entity labels     |
| ------- | --------------- | ----------------- |
| CDR     | 500             | Chemical, Disease |


**Agent design.** Three top-level agents and one compound loop implement sentence-level NER (Fig. S2, **Table S2**): LLM sentence splitting (`text_sentence_split`), a loop node (`ner_sentence_loop`) that iterates over sentences and runs HunFlair2 tagging on each sentence via the nested PGM agent `ner_flair_sent`, then PGM metric calculation (`eval_metrics`) on document-level merged entities. Gold labels are read from the CDR test CSV into workflow **START** as `expected_entities`.

**Table S2.** Agent and flow-node specifications for the sentence-level NER workflow.

Shipped workflow `**wf_doc_ner_flair_sent_eval`**: `text_sentence_split` → `ner_sentence_loop` (foreach over `sentences`; body: `ner_flair_sent`) → `eval_metrics` (Fig. S2). LLM model is configurable (e.g. Mistral 7B via Ollama); Flair uses HunFlair2 in the `flair` sandbox.


| Name (agent / node id) | Type            | Description                                                                                                                                  | Inputs                                                     | Outputs                             |
| ---------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------- |
| `text_sentence_split`  | LLM             | Split document text into a JSON array of sentences                                                                                           | `text`                                                     | `sentences`                         |
| `ner_sentence_loop`    | Loop            | `foreach` over `sentences`; run body agent `ner_flair_sent` on each sentence; merge per-iteration `predicted` into document-level `entities` | `sentences`, `labels`                                      | `entities` (merged)                 |
| `ner_flair_sent`       | PGM (loop body) | HunFlair2 NER via Flair plugin (`flair` sandbox); one sentence per iteration                                                                 | `sentence`, `labels`                                       | `predicted` (label → mention lists) |
| `eval_metrics`         | PGM             | Entity-level precision, recall, and F1 (micro/macro via metrics plugin)                                                                      | `predicted` / `entities`, `expected` / `expected_entities` | `metrics`                           |


**Workflow.** Fig. S2 / runner id `**wf_doc_ner_flair_sent_eval`**: `START` → `text_sentence_split` → `ner_sentence_loop` (`ner_flair_sent` nested in the loop) → `eval_metrics` → `END`.

**Implementation effort.** **Table S3** details the source code line counts of each node in the NER task implemented by NeuraGraph. **Table S4** presents the source code line counts of the Custom Python implementation for the same NER task. Line counts exclude blank lines. See main text Table 3 for Dify (`comparison/dify_tools_ner.py`, 134 lines).

**Table S3.** Source code lines of NeuraGraph for NER task.


| Node                            | Lines  |
| ------------------------------- | ------ |
| Sentence split                  | 0      |
| Flair NER                       | 24     |
| Performance metrics calculation | 11     |
| **Total**                       | **35** |


**Table S4.** Source lines of Custom Python for NER task.


| File                            | Lines   |
| ------------------------------- | ------- |
| custom_python_ner               | 63      |
| data parser                     | 169     |
| Data loader                     | 53      |
| Performance metrics calculation | 76      |
| **Total**                       | **361** |


**Execution and report.** The workflow was run on the CDR test set; Fig. S3 shows an auto-generated report (micro/macro metrics and qualitative analysis).

**Persistence.** Each instance is stored in `states.json` with `text`, `sentences`, `expected` / `predicted` entities, and per-instance `metrics`.

### 3.2 A workflow for chemical-induced-disease relation extraction

**Dataset.** BioCreative V CDR corpus; CID relation evaluation uses a **20-article** test subset for per-instance reporting (**Table S5**, **Table S10**). Full-document NER uses the 500-article test split (§3.1, **Table S1**).

**Table S5.** Benchmark subset (CID relation extraction).


| Dataset | # Test articles | Relation type            |
| ------- | --------------- | ------------------------ |
| CDR     | 20              | Chemical-induces-Disease |


**Agent design.** Three top-level agents and one compound loop implement chemical-induced-disease (CID) relation extraction (Fig. S4, **Table S6**): LLM hypernym filtering (`ontology_hypernym_filter`), PGM candidate pair generation (`cid_pair_generate`), and a loop node (`cid_re_verify_loop`) that iterates over `pairs` and runs LLM relation verification (`relation_verify_llm`) followed by PGM MeSH ID pair formatting (`relation_result_to_id_pair`) on each pair. Gold entity annotations, abstract text, and relation labels are read from the CDR subset CSV into workflow **START** (`entities`, `text`, `gold_relations`). Relation-level precision, recall, and F1 are computed from workflow graph metrics (`relation_pairs` in the workflow JSON) without a separate metrics agent node.

**Table S6.** Agent and flow-node specifications for the CID–RE workflow (`wf_cid_re_llm_linear`).

Shipped workflow `**wf_cid_re_llm_linear`**: `ontology_hypernym_filter` → `cid_pair_generate` → `cid_re_verify_loop` (foreach over `pairs`; body: `relation_verify_llm` → `relation_result_to_id_pair`) → `END` (Fig. S4). LLM steps use a configurable chat model (e.g. DeepSeek or GPT-4o via API/Ollama).


| Name (agent / node id)       | Type            | Description                                                                                     | Inputs                                                 | Outputs                     |
| ---------------------------- | --------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------- |
| `ontology_hypernym_filter`   | LLM             | Drop same-type hypernym rows from gold entity list (MeSH id hierarchy)                          | `entities`                                             | `filtered_entities`         |
| `cid_pair_generate`          | PGM             | Enumerate chemical–disease candidate pairs from filtered entities                               | `filtered_entities`                                    | `pairs`                     |
| `cid_re_verify_loop`         | Loop            | `foreach` over `pairs`; run body agents; merge verified relations                               | `pairs`, `text`                                        | `relations` (merged)        |
| `relation_verify_llm`        | LLM (loop body) | Binary verdict: chemical **induces** vs **does not induce** the disease (from abstract context) | `text`, `head`, `tail`                                 | `result`                    |
| `relation_result_to_id_pair` | PGM (loop body) | Format accepted pairs as MeSH id lines; negation/association guards                             | `result`, `head_id`, `tail_id`, `text`, `head`, `tail` | `relations` (per iteration) |
| Graph metrics                | Workflow config | Compare predicted `relations` to `gold_relations`                                               | `gold_relations`, `relations`                          | `rel_*` in `states.json`    |


**Workflow.** Fig. S4 / runner id `**wf_cid_re_llm_linear`**: `START` → `ontology_hypernym_filter` → `cid_pair_generate` → `cid_re_verify_loop` (`relation_verify_llm` and `relation_result_to_id_pair` nested in the loop) → `END`.

**Implementation effort.** **Table S7** details the source code line counts of each node in the RE task implemented by NeuraGraph. **Table S8** and **Table S9** compare Custom Python and Dify tool implementations for the same task. Line counts exclude blank lines.

**Table S7.** Source code lines of NeuraGraph for RE task.


| Node                       | Lines  |
| -------------------------- | ------ |
| Ontology hypernym filter   | 0      |
| Create entity pairs        | 24     |
| Relationship verification  | 0      |
| Relation result to ID pair | 61     |
| **Total**                  | **85** |


**Table S8.** Source lines of Custom Python for RE task.


| File                            | Lines   |
| ------------------------------- | ------- |
| custom_python_re                | 68      |
| data parser                     | 169     |
| Data loader                     | 53      |
| Performance metrics calculation | 76      |
| **Total**                       | **366** |


**Table S9.** Source code lines of Dify tools for RE task.


| Component     | Lines |
| ------------- | ----- |
| Dify_tools_re | 197   |


**Results.** **Table S10** lists per-article precision, recall, and F1 on the 20-article subset. **Micro:** P=0.595, R=0.962, F1=0.735 (TP=25, FP=17, FN=1). **Macro:** P=0.727, R=0.975, F1=0.798. Dominant errors are false-positive disease associations on high-recall articles (e.g. Articles 1, 9, 10).

**Table S10.** Per-instance metrics (CID–RE, 20-article subset).


| Article   | P         | R         | F1        | TP     | FP     | FN    |
| --------- | --------- | --------- | --------- | ------ | ------ | ----- |
| 1         | 0.333     | 1.000     | 0.500     | 1      | 2      | 0     |
| 2         | 1.000     | 1.000     | 1.000     | 2      | 0      | 0     |
| 3         | 0.500     | 0.500     | 0.500     | 1      | 1      | 1     |
| 4         | 0.667     | 1.000     | 0.800     | 2      | 1      | 0     |
| 5         | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 6         | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 7         | 1.000     | 1.000     | 1.000     | 2      | 0      | 0     |
| 8         | 1.000     | 1.000     | 1.000     | 2      | 0      | 0     |
| 9         | 0.333     | 1.000     | 0.500     | 2      | 4      | 0     |
| 10        | 0.200     | 1.000     | 0.333     | 1      | 4      | 0     |
| 11        | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 12        | 0.500     | 1.000     | 0.667     | 1      | 1      | 0     |
| 13        | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 14        | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 15        | 0.500     | 1.000     | 0.667     | 1      | 1      | 0     |
| 16        | 0.500     | 1.000     | 0.667     | 1      | 1      | 0     |
| 17        | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 18        | 1.000     | 1.000     | 1.000     | 1      | 0      | 0     |
| 19        | 0.500     | 1.000     | 0.667     | 1      | 1      | 0     |
| 20        | 0.500     | 1.000     | 0.667     | 1      | 1      | 0     |
| **Micro** | **0.595** | **0.962** | **0.735** | **25** | **17** | **1** |
| **Macro** | **0.727** | **0.975** | **0.798** | —      | —      | —     |


**NOTE (Table S10).** TP: correct chemical–induces–disease pairs; FP: predicted relation not in gold; FN: missed gold relation.

### 3.3 Tuning-driven refinement (reporting evaluation)

We evaluated workflow tuning on a **20-article tuning set** and a separate **5-article test set** (random seed 42), using the CID relation workflow described in §3.2. The built-in **experiment wizard** ran four steps: (1) execute the baseline workflow on both sets and record per-article errors; (2) produce an LLM **tuning report** that summarizes false positives and false negatives with example abstracts; (3) turn that report into **concrete edit proposals** (prompt text for the relation verifier, Python guards for post-processing); (4) apply each proposal to a copy of the workflow and **re-run only the tuning set**—keeping the change only if tuning F1 improved. **Table S11** lists **test** metrics before and after optimization.

**Table S11.** Tuning-loop evaluation (5-article test).


| Stage          | Precision | Recall | F1    |
| -------------- | --------- | ------ | ----- |
| Baseline test  | 0.667     | 0.800  | 0.720 |
| Optimized test | 0.813     | 1.000  | 0.874 |


**Baseline tuning report (F1 0.435).** The LLM report pointed to two main problems on the 20-article tuning set: **(1) verifier too strict**—many gold relations were missed because the model treated hedged or associative wording (*associated with*, *may cause*, *side effect of*, etc.) as **does not induce**; **(2) post-processing too aggressive**—after the verifier said **induces**, a nearby-word filter (100-character window) sometimes dropped valid pairs when cue words such as “side effects” appeared close to the entities (e.g. *zidovudine* and *megaloblastosis*). It also listed **false positives** where the verifier said **induces** but the sentence negated causation (e.g. “did not …” near *norepinephrine* and *catatonia*).

**Refinement.** The report proposed **two edits**, applied one at a time; each was kept only if tuning F1 rose (details in `result/opt_compare_20260529_143039.json`).

**Round 1.** Relax relation-verifier prompts (**Table S12**).

**Table S12.** Optimization round 1: relation verifier prompts.


| Aspect    | Summary                                                                                                                                                                                                                                                      |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Problem   | Verifier required explicit “X caused Y” wording; missed valid CID relations with softer causal language.                                                                                                                                                     |
| Change    | Rewrote system and user prompts to accept implied causation (*associated with*, *risk factor*, *may cause*, *due to*, *side effect of*, *induced by*, etc.) while still rejecting pre-existing disease, bare co-occurrence, speculation, and clear negation. |
| Tuning F1 | **0.435 → 0.529** (report quality score 8/10 → 10/10).                                                                                                                                                                                                       |


**Round 2.** Adjust post-processing guards (**Table S13**).

**Table S13.** Optimization round 2: relation post-processing.


| Aspect    | Summary                                                                                                                                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Problem   | 100-character “associative phrase” window blocked true relations (e.g. *zidovudine* → *megaloblastosis*); negation in text was not always caught after a false **induces** verdict.                                             |
| Change    | When the verdict is **induces**, drop the pair if negation phrases occur within 50 characters of the entities; otherwise apply a softer associative filter only within **30** characters (not 100); else keep the MeSH ID pair. |
| Tuning F1 | **0.529 → 0.612** (report quality score 10/10).                                                                                                                                                                                 |


**Held-out test.** After both rounds, the updated workflow was evaluated once on the 5-article test set without further edits (**Table S11**): micro-averaged F1 rose from **0.720** to **0.874** (**+0.154** absolute), with recall **1.000**.

The wizard links **diagnostic reporting** on the tuning set (Tables S12–S13) to **held-out test gains** (Table S11); automated report scoring aligned with tuning F1 improvements (8/10 → 10/10 after round 1).

*Source: `result/opt_compare_20260529_143039.json`; test split seed 42.*

### 3.4 Full performance evaluation (pharmacovigilance use case)

To address end-to-end system assessment on a realistic pharmacological task, we evaluate NeuraGraph on the **BioCreative V Chemical–Disease Relation (CDR)** corpus under a **pharmacovigilance-oriented use case**: mining **chemical-induced disease (CID)** assertions from biomedical abstracts (e.g. drug toxicity, treatment-emergent adverse events, and other drug–disease causal mentions). The same benchmark underpins section 3.1 (NER) and 3.2 (CID–RE); section 3.3 reports workflow optimization on a small development split. Section 3.4 reports **frozen-workflow** performance on the **official 500-article test split**: hybrid vs LLM NER within NeuraGraph (Task A), CID–RE with oracle entities (Task B), and end-to-end **Flair NER → optimized RE** (Task C).

**Use case.** Given PubMed-style title+abstract text, the system (1) tags **Chemical** and **Disease** mentions, (2) verifies which chemical–disease pairs are supported as CID (chemical **induces** disease) in context, and (3) logs micro/macro precision, recall, and F1 with per-article experiment logs for audit. This mirrors literature-based pharmacovigilance screening where relation quality matters as much as entity coverage.

**Datasets and splits.** Gold annotations use the BC5CDR PubTator release (`test.txt` and `dev.txt`; 500 articles each). Batch CSVs are generated with the built-in CID dataset builder (stratified tuning split, test extraction). **Table S14** summarizes splits; **no test-set tuning**—prompt and PGM edits and the experiment wizard (section 3.3) use **dev** only; all **Tables S16–S18** numbers use frozen workflows saved before the test batch runs.

**Table S14.** Performance evaluation — datasets and splits.


| Split                  | Source         | # Articles      | Role                                       | Batch CSV                              |
| ---------------------- | -------------- | --------------- | ------------------------------------------ | -------------------------------------- |
| Test (primary)         | CDR `test.txt` | 500             | Final micro/macro metrics (Tables S16–S18) | `cdr_test_500.csv`                     |
| Dev — tuning (50)      | CDR `dev.txt`  | 50 (stratified) | Task B tuning + refiner (Tables S15B, S16b) | `cid_dev_tuning_stratified_50.csv`     |
| Dev — tuning (20)      | CDR `dev.txt`  | 20 (stratified) | Legacy wizard example (section 3.3)      | `cid_dev_tuning_stratified.csv`        |
| Dev — tuning remain    | CDR `dev.txt`  | 480             | Internal validation; optional              | `cid_dev_test_remain.csv`              |
| Dev — small held-out   | CDR `dev.txt`  | 5 (seed 42)     | Optimization smoke test (Table S11)        | `cid_dev_test_custom_sample_5_s42.csv` |
| Illustrative RE subset | CDR `dev.txt`  | 20              | Per-article Table S10 (section 3.2)        | `cid_dev_test_custom.csv` (subset)     |


**Evaluation protocol.**

1. **NER (Task A).** Run `wf_doc_ner_flair_sent_eval` (Flair/HunFlair2 sentence loop, section 3.1) and `wf_doc_ner_llm_eval` (document LLM NER) on `cdr_test_500.csv`. Metrics: entity-level micro/macro P/R/F1; optional per-label Chemical vs Disease breakdown in supplementary notes.
2. **CID–RE (Task B).** Run `wf_cid_re_llm_linear` with gold entities in CSV (upper bound for the relation module). Report **baseline** workflow and **optimized** workflow (`wf_cid_re_llm_linear_opt_`* tuned on dev per section 3.3).
3. **CID–RE, end-to-end (Task C).** Replace CSV entities with **Flair NER** predictions from Task A (`wf_doc_ner_flair_sent_eval` on `cdr_test_500.csv`), then run the frozen optimized CID workflow (`wf_cid_re_llm_linear_opt_`*). Quantifies error propagation from hybrid NER to pharmacovigilance relation mining. LLM NER is **not** chained into Task C (reported only in Table S16). A **Custom Python RE** reference (micro-P 0.75, micro-R 0.81, micro-F1 0.78; prior dev-scale run, Table S8) is listed in **Table S18** for comparison only—**not re-executed** on the 500-article test split.

**Reproducibility.** Batch experiments are designed so a completed run can be audited and repeated under the same configuration. The platform stores the workflow that was executed, a snapshot of each agent and tool definition as it stood when the workflow was saved (so later edits in the visual editor do not change what an old experiment actually ran), and per-article logs of inputs, intermediate outputs, predictions, and evaluation metrics. Re-running or reviewing an experiment therefore uses the stored workflow and agent snapshots rather than whatever happens to be loaded in the editor at review time. LLM-based steps are inherently stochastic; repeats are comparable only when the same model, endpoint, and sampling settings are kept and recorded alongside the run.

**Table S15.** Experiment registry (BC5CDR test 500).


| Task | Method                                    | Runner                                                      | Experiment id                          |
| ---- | ----------------------------------------- | ----------------------------------------------------------- | -------------------------------------- |
| A    | NeuraGraph Flair NER                      | `wf_doc_ner_flair_sent_eval`                                | `064f47ac-2d08-4e9a-85e3-2ca2e564c7da` |
| A    | NeuraGraph LLM NER                        | `wf_doc_ner_llm_eval`                                       | `aba808f2-46ad-4585-984f-633955729315` |
| B    | NeuraGraph RE (test 500 + dev50 wizard)    | `wf_cid_re_llm_linear`                                      | `678a855f-1f8a-492e-9d39-be37df122795` |
| B    | NeuraGraph RE (optimized, test 500)        | `wf_cid_re_llm_linear_opt_20260604`                         | `f860e6d3-51fd-4b24-aa51-3d0fb9c88907` |
| C    | NeuraGraph E2E (Flair NER → optimized RE) | `wf_e2e_flair_opt_re`                                       | `bffea244-c3dd-4b97-98f2-9ed4d7bb895a` |


**Table S15B.** Dev50 tuning sub-experiments under test-500 parent `678a855f` (oracle entities, n=50). In the UI, open **http://127.0.0.1:5001/exp/678a855f-1f8a-492e-9d39-be37df122795** → wizard **Tab 3 (Tuning & Optimize)** to view tuning baseline report, accepted refinement metrics, and optimize-loop summary; sub-run ids are linked from that page.


| Stage | Parent / sub-exp | Workflow / agent pin | Effective agents | Experiment id |
| ----- | ---------------- | -------------------- | ---------------- | ------------- |
| Test-500 baseline (wizard parent) | parent | `wf_cid_re_llm_linear` | `relation_verify_llm` v0010; `relation_result_to_id_pair` v0003 | `678a855f-1f8a-492e-9d39-be37df122795` |
| Tuning baseline (phase 1) | sub | `wf_cid_re_llm_linear` | v0010; v0003 | `opt_base_tune_81781d50` |
| Accepted refinement | sub | `wf_cid_re_llm_linear` | `relation_verify_llm` **v0013** (Condition 2 DDI only) | `opt_cand_ddi_c2_8cb2b66e` |
| Frozen tuned graph *(export pending)* | — | `wf_cid_re_llm_linear_opt_20260609` | v0013; v0003 | test-500 re-run pending (Table S17) |


**Table S16.** NER on BC5CDR test (n=500). Entity-level metrics; gold = `gold_entities` in CSV.


| Method                                    | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 |
| ----------------------------------------- | ------- | ------- | -------- | ------- | ------- | -------- |
| NeuraGraph (`wf_doc_ner_flair_sent_eval`) | 0.725   | 0.840   | 0.779    | 0.737   | 0.844   | 0.779    |
| NeuraGraph (`wf_doc_ner_llm_eval`)        | 0.640   | 0.673   | 0.656    | 0.672   | 0.690   | 0.667    |


*Table S16 (Flair row): batch run on `cdr_test_500.csv` (experiment `064f47ac-2d08-4e9a-85e3-2ca2e564c7da`, completed 2026-06-03). Micro: aggregate TP/FP/FN over 500 articles; macro: mean of per-article P/R/F1.*

*Table S16 (LLM row): `scripts/run_perf_ner_test500.py --runner wf_doc_ner_llm_eval` (experiment `aba808f2-46ad-4585-984f-633955729315`, completed 2026-06-04). Same metric protocol as Flair row.*

**RE tuning on dev50 (Task B).** Pharmacovigilance CID–RE was tuned on a **stratified 50-article** subset of CDR `dev.txt` (`cid_dev_tuning_stratified_50.csv`; same builder as §3.3). Oracle **gold entities** in CSV include multiple surface strings per MeSH id (synonyms); evaluation maps predicted and gold relation endpoints to **head MeSH id | tail MeSH id** via `normalize_cid_lines` and the per-article entity list. The baseline workflow `wf_cid_re_llm_linear` was updated before tuning: **llmre** `RE.induce` verifier prompt (`prompt_templates.json`, induce block), PGM **`cid_entities_dedupe_mesh`** (one row per MeSH id before hypernym filter), and hypernym-filter instructions to collapse synonym rows.

**Protocol (phases 1–3).** All steps are launched from the test-500 parent experiment **`678a855f-1f8a-492e-9d39-be37df122795`** (wizard Tab 1: baseline test on `cdr_test_500.csv`; Tab 3: tuning on `cid_dev_tuning_stratified_50.csv`). (1) **Tuning baseline** — sub-exp `opt_base_tune_81781d50` (`relation_verify_llm` v0010 + `relation_result_to_id_pair` v0003). (2) **Tuning report** — LLM report on FP/FN exemplars (`result/opt_base_tune_81781d50/report_tuning_baseline.md`). (3) **`agent_refiner`** — biomedical semantic edits to the LLM verifier; kept only if macro-averaged tuning F1 rose. Accepted change: refine **Condition 2** with drug–drug interaction clinical phrasing → `relation_verify_llm` **v0013** (sub-exp `opt_cand_ddi_c2_8cb2b66e`). Frozen graph `wf_cid_re_llm_linear_opt_20260609` and test-500 re-evaluation are pending (Table S17).

**Table S16b.** Dev50 tuning — baseline and accepted refinement (oracle entities, n=50). **Micro** = corpus-level P/R/F1 from summed TP/FP/FN; **macro** = mean of per-article P/R/F1. Sub-experiments are nested under parent `678a855f` (Table S15B).


| Stage | Workflow / agent | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 | TP | FP | FN | ΔMacro-F1 |
| ----- | ---------------- | ------- | ------- | -------- | ------- | ------- | -------- | -- | -- | -- | --------- |
| Tuning baseline (v0010) | `opt_base_tune_81781d50` | 0.583 | 0.750 | 0.656 | 0.610 | 0.757 | 0.642 | 141 | 101 | 47 | — |
| Accepted refinement (v0013) | `opt_cand_ddi_c2_8cb2b66e` | 0.603 | 0.761 | 0.673 | 0.626 | 0.791 | 0.666 | 143 | 94 | 45 | **+0.024** |


*Tuning baseline sub-exp `opt_base_tune_81781d50` (completed 2026-06-09). Accepted candidate `opt_cand_ddi_c2_8cb2b66e` (`relation_verify_llm` v0013). View reports and optimize summary in the UI at `/exp/678a855f-1f8a-492e-9d39-be37df122795` (wizard Tab 3).*

**Tuning report (macro-F1 0.642).** On the v0010 verifier, **47 FNs** cluster where the LLM returns `~` despite true CID: **sample 12** (cisapride–diltiazem interaction → QT prolongation / torsades; Condition 2 not matched), **sample 24** (ifosfamide toxicity list), **sample 6** (`ifosfamide-induced emesis`). **101 FPs** cluster where `$` is returned for non-causal pairs: **sample 33** (serotonin-syndrome article — diazepam treatment, endogenous mediators), **sample 15** (angiotensin as physiological substance), **sample 7** (creatinine as lab marker).

**Accepted refinement.** `agent_refiner` was rewritten to propose **biomedical semantic** edits to the LLM verifier only (no PGM/process patches). Offline ablation on dev50 identified one positive change: refine **Condition 2** with drug–drug interaction clinical phrasing (`{head}-{other drug} interaction`, `{other drug}-{head} interaction`, `co-administration of {head}`). Sub-exp `opt_cand_ddi_c2_8cb2b66e` → macro-F1 **0.666** (Δ **+0.024**), micro-F1 **0.673** (Δ **+0.017**); TP +2, FP −7, FN −2. Saved as `relation_verify_llm` **v0013**. Artifact: `result/opt_base_tune_81781d50/surgical_variant_test.json`.

**Table S17.** CID relation extraction on BC5CDR test (n=500) — **oracle entities** (gold entities in CSV). Relation type: Chemical-induces-Disease (MeSH id pairs).


| Method                                                                    | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 | TP  | FP    | FN  |
| ------------------------------------------------------------------------- | ------- | ------- | -------- | ------- | ------- | -------- | --- | ----- | --- |
| NeuraGraph RE (baseline, `wf_cid_re_llm_linear`)                          | 0.489   | 0.853   | 0.622    | 0.573   | 0.869   | 0.647    | 909 | 949   | 157 |
| NeuraGraph RE (optimized, `wf_cid_re_llm_linear_opt_20260604`, dev-tuned) | 0.505   | 0.668   | 0.575    | 0.575   | 0.766   | 0.608    | 712 | 698   | 354 |


*Table S17 (test 500): Baseline oracle-RE batch on `cdr_test_500.csv` (exp `678a855f`, `wf_cid_re_llm_linear`; micro-F1 0.622, macro-F1 0.647; run failed at sample 191/500 — partial n=190). Effective agents: `relation_verify_llm` v0010, `relation_result_to_id_pair` v0003. Optimized row: `wf_cid_re_llm_linear_opt_20260604` (exp `f860e6d3`, micro-F1 0.575, macro-F1 0.608). Test-500 re-run with dev50-tuned verifier **v0013** (`wf_cid_re_llm_linear_opt_20260609`, Table S15B) is pending.*

**Table S18.** CID relation extraction on BC5CDR test (n=500) — **end-to-end** (Flair NER predictions from Task A → frozen optimized RE).


| Method                                               | RE workflow           | Micro-P | Micro-R | Micro-F1 | Macro-F1 |
| ---------------------------------------------------- | --------------------- | ------- | ------- | -------- | -------- |
| NeuraGraph Flair NER → optimized RE                  | `wf_e2e_flair_opt_re` | 0.543   | 0.765   | 0.635    | 0.663    |
| PubTator3 (NER + RE, via PubTator3 API)              | `wf_e2e_pubtator_re`  | 0.396   | 0.627   | 0.485    | 0.498    |


*Table S18 (E2E row, n=500): merged experiment `bffea244-c3dd-4b97-98f2-9ed4d7bb895a` (`scripts/merge_e2e_states.py --500` on `cdr_test_500.csv`). Workflow `wf_e2e_flair_opt_re`: Flair sentence NER (`sg_e2e_flair_ner`) → optimized CID RE (`sg_e2e_cid_re`). Segment exps: `f859b257` (1–20), `309d1c78` (21–30), `a728966d` (31–50), `576ead7a` (51–100), `031fff5a` (101–199), `68ff0297` (200–500). Micro: TP=724, FP=609, FN=223; macro: mean per-article P/R/F1. Same relation-pair metric protocol as Table S17.*

**Error analysis (summary).** After batch runs, aggregate false positives and false negatives on a stratified test subset (e.g. 50 articles). Section 3.2 **Table S10** remains a **20-article** worked example on dev.

**Relation to sections 3.2–3.3.** Section 3.2 reports per-article metrics on a 20-article dev subset (Table S10). Section 3.3 demonstrates the tuning wizard (Table S11). **Tables S16–S18** provide primary publication metrics on the 500-article test split.

*Task A (LLM NER row): `py -3 scripts/run_perf_ner_test500.py --runner wf_doc_ner_llm_eval`.*

---

## 4. Pre-built component inventory

The distribution includes **47** pre-built agents (**21** LLM-based, **26** programmatic/PGM) covering end-to-end biomedical text mining, together with **9** reusable subgraphs orchestrated via native **loop** and **branch** flow nodes, **19** reference workflows, **12** callable tools, and native parsers for **CDR**, **ChemDisGene**, and plain text. Component ids match files under `meta/agents/`, `meta/graphs/`, and `meta/tools/` in release v2.x (workflow optimization copies with `_opt_YYYYMMDD` timestamps and auto-generated `ner_flair_sent_loop` are excluded from the workflow count).

### 4.1 Agents (47)

**Table S19. LLM agents (21)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `agent_refiner` | Agent Refiner (LLM) | Generate actionable agent modifications from experiment diagnostics. |
| 2 | `e2e_hypernym_filter` | E2E Hypernym Filter (LLM) | Remove hypernyms and standalone modifiers from entity list using article context; keep only the most specific entities per concept. |
| 3 | `e2e_synonym_filter` | E2E Synonym Filter (LLM) | Assign every input entity to a synonym cluster (shared id); do not drop entities. |
| 4 | `kg_triple_extract_llm` | Triple Extraction (LLM) | Biomedical knowledge-graph triple extraction |
| 5 | `ner_comparison_report` | NER Comparison Report | Generates a comparison report between Flair and LLM NER results |
| 6 | `ner_from_tree_llm` | NER from Dependency Tree (LLM) | Extract entities from CoNLL-U dependency tree |
| 7 | `ner_llm` | NER (LLM, configurable types) | Extract biomedical named entities from text |
| 8 | `ontology_entity_link` | Entity Linking / Normalization (LLM) | Canonicalize entity mentions for knowledge-graph linking |
| 9 | `ontology_hypernym_filter` | Hypernym Filter (LLM) | Identify same-type hypernyms by MeSH id; drop hypernym rows from entity list |
| 10 | `ontology_synonym_resolve` | Synonym Resolution (LLM) | Biomedical abstract synonym extraction (aligned with synonym_extraction) |
| 11 | `relation_extract_llm` | Relation Extraction (LLM) | Strict biomedical CID relation verifier for chemical–disease pairs |
| 12 | `relation_from_tree_llm` | Relation Extraction from Tree (LLM) | Extract [head entity, verb, tail entity] triples from CoNLL-U dependency tree |
| 13 | `relation_verify_llm` | Relation Verification (LLM) | CID induce verifier (llmre prompt_templates.json RE.induce, lines 17-23) |
| 14 | `report_comparator` | Report Comparator (LLM) | Compare baseline vs candidate experiment outcomes and report quality. |
| 15 | `report_experiment` | Experiment Report (LLM) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| 16 | `report_experiment_tool` | Experiment Report (LLM + Tools) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| 17 | `syntax_dep_parse` | Dependency Parse (CoNLL-U) | English sentence to CoNLL-U dependency tree |
| 18 | `text_coreference` | Coreference Resolution (LLM) | Biomedical abstract coreference resolution |
| 19 | `text_sentence_split` | Sentence Split (LLM) | English sentence splitting for biomedical abstract |
| 20 | `text_summarize` | Text Summarization (LLM) | Summarize text into 2-3 sentences |
| 21 | `text_word_segment` | Word Segmentation (LLM) | English word segmentation |

**Table S20. PGM agents (26)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `cid_entities_dedupe_mesh` | CID Entities Dedupe (MeSH id) | Collapse oracle entities that share a MeSH id (synonyms) to one row per id before hypernym filter and pair generation. |
| 2 | `cid_pair_generate` | CID Pair Generator (PGM) | Builds chemical–disease head/tail text pairs with MeSH IDs from filtered Chemical and Disease entities. |
| 3 | `dataset_cid_tuning_build` | CID Tuning Dataset Builder (PGM) | Builds CID relation tuning and test splits from a PubTator source file via the CidDatasetBuilder plugin. |
| 4 | `e2e_entities_assign_group_ids` | E2E Assign Synonym Group IDs (PGM) | Assign shared numeric ids (1, 2, ...) per label to synonym groups; all surface forms in a group share the same id. |
| 5 | `e2e_entities_dedup_by_id` | E2E Entities Dedup By ID | Deduplicate entities by shared id; keep shortest surface form per id group. |
| 6 | `e2e_entities_passthrough` | E2E Entities Passthrough | Dedupe Flair NER entities and use surface text as id when MeSH id is missing (E2E RE path). |
| 7 | `e2e_entity_aliases_snapshot` | E2E Entity Aliases Snapshot (PGM) | Preserve all synonym surface forms + shared numeric ids for metrics lookup (before dedup). |
| 8 | `eval_flair` | Auto FLAIR NER Metrics | Counts unique FLAIR NER entities per label and returns total and per-label entity counts. |
| 9 | `eval_llm` | Auto LLM NER Metrics | Counts unique LLM NER entities per label and returns total and per-label entity counts. |
| 10 | `eval_metrics` | Evaluation Metrics (PGM) | Computes NER precision, recall, and F1 by comparing predicted and expected entity sets via MetricsCalculation. |
| 11 | `eval_metrics_relation` | Relation Set Metrics (PGM) | Evaluates chemical–induced-disease relation sets by normalizing and comparing predicted relations to ground truth. |
| 12 | `eval_metrics_segment` | Segmentation Metrics (PGM) | Scores pipe-delimited word segmentation by boundary precision, recall, F1, and segmentation error analysis. |
| 13 | `eval_pair_generate` | Evaluation Pair Generator (PGM) | Generates all chemical–disease evaluation pairs from expected Chemical and Disease entity lists. |
| 14 | `kg_rdf_export` | RDF-JSON Export (PGM) | Exports knowledge-graph triples to RDF-JSON with node labels and subject–predicate–object edges. |
| 15 | `kg_triple_merge` | Triple Merge (PGM) | Merges pipe-delimited relations with entity-link canonicalization and deduplicates head–predicate–tail triples. |
| 16 | `kg_triple_persist` | Triple CSV Persistence (PGM) | Persists merged knowledge-graph triples to CSV under result with head, verb, and tail columns. |
| 17 | `llm_link_bulk_update` | Bulk LLM Link Update (PGM) | Bulk-updates LLM connector links on selected agents from a source model to a target, optionally dry-run. |
| 18 | `merge_metrics` | Merge Flair and LLM Metrics | Combines FLAIR and LLM NER metric dictionaries into a single merged_metrics report object. |
| 19 | `ner_entities_to_re_format` | NER Entities to RE Format | Converts Flair NER label dict {Chemical:[...], Disease:[...]} to the entity list format [{text, label, id}] expected by the CID RE pipeline. |
| 20 | `ner_flair_aggregate` | Flair NER Aggregator | Aggregates per-sentence FLAIR NER outputs into document-level label-to-unique-entity-text dictionaries. |
| 21 | `ner_flair_doc` | NER (Flair, document) | Runs HunFlair2 NER on a document split into sentences and returns deduplicated entities per label. |
| 22 | `ner_flair_sent` | NER (Flair, sentence) | Tags one sentence with HunFlair2 NER and returns predicted entity texts grouped by label. |
| 23 | `relation_extract_pubtator` | Relation Extraction (PubTator) | Extracts chemical–disease relations from text or PMID using PubTator3 and local entity annotations. |
| 24 | `relation_result_to_id_pair` | Relation Result -> ID Pair | Emits head_id/tail_id CID relation lines when verification is positive, with negation and weak-association guards. |
| 25 | `relation_verify_to_pair` | Relation Verify → Entity Pair | Maps a positive relation verification to canonical head and tail entity IDs from entity_link. |
| 26 | `report_format_json` | Result Formatter (PGM) | Formats original text and summary into JSON with character lengths for reporting pipelines. |

### 4.2 Reusable subgraphs (9)

**Table S21. Reusable subgraphs (9)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `sg_cid_re_verify` | CID RE verify pair | Verify one Chemical–Disease pair; output MeSH id pair when verdict is induces. |
| 2 | `sg_e2e_cid_re` | E2E CID RE (subgraph) | Subgraph: passthrough → synonym → assign ids → alias snapshot → dedup → hypernym → pair gen → verify loop. |
| 3 | `sg_e2e_flair_ner` | E2E Flair NER (subgraph) | Subgraph: sentence split → loop HunFlair2 per sentence → RE format entities. Input: text + labels. Output: entities as [{text, label, id}]. |
| 4 | `sg_e2e_pubtator_re` | E2E PubTator3 RE (subgraph) | Subgraph: PubTator3 API → CID relations. Input: text + pmid. Output: relations as head_id / CID / tail_id lines. |
| 5 | `sg_ner_flair_sent` | Sentence Flair NER | Run ner_flair_sent on one sentence (loop body). |
| 6 | `sg_preprocess_inner` | Inner preprocess loop body | Format / pass-through inner loop step. |
| 7 | `sg_re_preprocess` | RE preprocess + NER | Nested inner loop then ner_llm (outer loop body for doc RE). |
| 8 | `sg_re_tree` | Tree-based RE | syntax_dep_parse → relation_from_tree_llm per sentence. |
| 9 | `sg_relation_verify` | Relation verify pair | relation_verify_llm → relation_verify_to_pair for one head/tail pair. |

### 4.3 Reference workflows (19)

**Table S22. Reference workflows (19)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `wf_cid_ner_llm_eval` | CID NER Eval (LLM) | Chemical/Disease NER with LLM and generic metrics. |
| 2 | `wf_cid_re_branch` | CID RE (multi-branch gate) | NER then 4-way branch gate before relation extraction. |
| 3 | `wf_cid_re_llm_linear` | CID RE Pipeline (linear) | Gold entities → e2e dedup by id → e2e hypernym filter (with text context) → pair list → foreach RE verify → id pairs. Upgraded from wf_e2e_flair_opt_re agents. |
| 4 | `wf_doc_ner_flair_eval` | Doc NER Eval (Flair) | Document Flair NER with metrics (replaces bio_ner_graph). |
| 5 | `wf_doc_ner_flair_sent_eval` | Doc NER Eval (Flair, sentence) | Sentence split → loop HunFlair2 per sentence → entity metrics (Table S2 / Fig. S2). |
| 6 | `wf_doc_ner_llm_eval` | Doc NER Eval (LLM) | Split document then LLM NER with metrics. |
| 7 | `wf_doc_ner_loop_branch` | Doc NER loop + branch | Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics. |
| 8 | `wf_doc_re_nested_branch` | Doc RE (nested loop + branch) | Outer loop with nested preprocess + NER, 4-way branch, then RE. |
| 9 | `wf_e2e_flair_opt_re` | E2E Flair NER + Optimized RE | Flair sentence-split NER → optimized CID RE (v0008 prompt) → relation metrics. For Table S18. |
| 10 | `wf_e2e_pubtator_re` | E2E PubTator3 RE | Compose sg_e2e_pubtator_re (PubTator3 API → relations) → relation metrics vs gold_relations. For Table S18 comparison. |
| 11 | `wf_flair_vs_llm_ner` | Flair vs LLM NER Comparison | Sentence split, Flair loop NER, LLM NER, per-path metrics, and ner_comparison_report on the same document. |
| 12 | `wf_general_report_linear` | Summarize + format | Summarize text and pack into JSON result. |
| 13 | `wf_kg_flair_full` | KG Build (Flair NER) | Flair doc NER → entity link → triple extract → merge → RDF. |
| 14 | `wf_kg_llm_full` | KG Build (LLM NER) | LLM NER → entity link → RE → triple merge → RDF export. |
| 15 | `wf_kg_syntax_loop` | KG from syntax (sentence loop) | Coreference → split → loop tree-RE subgraph → CSV persist. |
| 16 | `wf_re_pubtator_dev10` | PubTator RE Dev (10) | BC5CDR dev.txt (10 articles): gold entities → PubTator3 relation extraction → relation pair metrics vs gold_relations. |
| 17 | `wf_re_pubtator_eval` | PubTator RE Eval | Gold entities → PubTator relation extraction → relation pair metrics. |
| 18 | `wf_re_verify_llm_loop` | RE Verify (pair loop) | Generate evaluation pairs → loop verify subgraph → metrics. |
| 19 | `wf_word_seg_llm_eval` | Word Segmentation Eval | LLM word segmentation with boundary metrics. |

### 4.4 Callable tools (12)

**Table S23. Callable tools (12)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `agent_change_impact_trace` | Agent Change Impact Trace | Estimate per-agent metric contribution from version_map and two experiment states. |
| 2 | `agent_version_guard` | Agent Version Guard | Policy-based guard for keep/alert/rollback decisions using metric deltas. |
| 3 | `dataset_cid_tuning_build` | CID Tuning Dataset Builder | Build a stratified CID tuning CSV (and optional test-remain set) from PubTator gold dev.txt. |
| 4 | `dataset_sampler_stratified` | Dataset Sampler Stratified | Stratified sample by text length, entity density, and relation density for quick A/B validation. |
| 5 | `error_case_exporter` | Error Case Exporter | Export worst-k error cases from states into markdown and jsonl payloads for review/regression. |
| 6 | `fn_fp_bucket_analyzer` | FN FP Bucket Analyzer | Bucket FN/FP into boundary/type/relation/missed-recall style categories with examples. |
| 7 | `merge_heads_tails_to_entities` | Merge Heads & Tails to Entities | Merge two lists of head/tail entities into a unified 'text,type,mesh' string format, one entity per line. |
| 8 | `metrics_delta_compare` | Metrics Delta Compare | Compare baseline and candidate states, return precision/recall/f1 deltas and significantly degraded samples. |
| 9 | `prompt_patch_apply_safe` | Prompt Patch Apply Safe | Apply structured prompt patch (append/replace/remove-rules) with validation and safety checks. |
| 10 | `report_quality_scorer` | Report Quality Scorer | Score report quality on evidence, executability, and traceability. |
| 11 | `tool_ner_flair` | NER by Flair | Input a sentence string, and label string like "Chemical,Disease", the tool will do NER task and return a dict like  {"Chemical":["a","b"], "Disease":["c","d"] } |
| 12 | `tool_pubtator_relation_extract` | PubTator Relation Extract | Call NCBI PubTator3 API (https://www.ncbi.nlm.nih.gov/research/pubtator3-api) to extract chemical–disease relations from a PubMed PMID or text. Returns relations as head / CID / tail lines. |

### 4.5 Native dataset parsers

**Table S24. Native dataset parsers (3)**

| No. | ID | Name | Description |
| --- | --- | --- | --- |
| 1 | `parser_cdr` | CDR (PubTator) | Load BioCreative V CDR PubTator .txt articles with gold entities and CID relations (CIDParser). |
| 2 | `parser_chemdisgene` | ChemDisGene | Load ChemDisGene article .txt files with companion .tsv annotation trees (ChemDisGeneParser). |
| 3 | `parser_plain_text` | Plain text (raw upload) | Load user-uploaded plain-text .txt from data/raw for batch runs without bundled gold files. |

Built-in loaders are selected automatically from dataset folder layout (`data/data_load.py`: PubTator .txt, ChemDisGene .tsv trees, or `data/raw` uploads).

---


## Algorithm S1. Automatic input inference


| Step | Action                                                                               |
| ---- | ------------------------------------------------------------------------------------ |
| 1    | Load graph metadata; obtain node list.                                               |
| 2    | Initialize sets of produced outputs and required inputs.                             |
| 3    | For each node, register its outputs; register inputs not satisfied by prior outputs. |
| 4    | Global inputs = inputs not produced by any upstream node.                            |
| 5    | Return sorted global input names.                                                    |


## Algorithm S2. Loop subgraph invocation (current implementation)


| Step | Action                                                                                                                         |
| ---- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1    | Load parent workflow; resolve `flowNodes[loop_id].subgraphId` → subgraph file `sg_`*.                                          |
| 2    | For each element of `loopConfig.array` (e.g. `pairs`, `sentences`): run one loop-body iteration with the current list element. |
| 3    | Execute subgraph (compiled LangGraph) for that item.                                                                           |
| 4    | Merge listed outputs via `mergeKeys` / default list merge into parent state.                                                   |
| 5    | Continue parent workflow after loop completes.                                                                                 |


---

## Sync checklist for Word (`supplementary_data.docx`)

- Replace Feature 2 SUB wording with loop + `sg_*` (Section 2).
- Replace Feature 3 with sandbox paragraph (Section 2).
- Add Feature 4; merge reporting + tuning into Feature 6 (six features total in §2).
- Update Table S2/S6 (loop/subgraph; RE pipeline nodes).
- Fix caption **Table 3** → **Table S3** in §3.1.
- Fix **Fig. 4** → **Fig. S4** for RE workflow.
- Add §3.3 with Tables S11–S13 (tuning).
- Update §1 inventory (47 agents, 9 sg, 19 wf).
- Add §3.4 performance evaluation (Tables S14–S18; S15B dev50 tuning registry; S16b v0013 DDI refinement; S18 E2E test-500 merged `bffea244`, micro-F1 0.635).
- Add §4 pre-built component inventory (Tables S19–S24: No., ID, Name, Description).
- Replace Algorithm 2 table with Algorithm S2 loop version.

