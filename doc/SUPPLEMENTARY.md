# Supplementary Material

This file is the revised supplementary text for the NeuraGraph Application Note (v2.x). Sync into `supplementary_data.docx` for submission. Figure/table numbers use **S** prefix; keep existing figure files (Fig. S2–S6) where paths still match.

---

## 1. Software architecture

NeuraGraph adopts a three-layer architecture (Fig. 1). The **Presentation Layer** provides a browser-based visual editor for drag-and-drop workflow assembly with real-time **input-inference validation**. The **Service Layer** (Flask API, LangGraph orchestration, plugins, LLM connectors) runs batch workflows, optional **sandbox sidecars** for heavy local models, and an **experiment wizard** (test/tuning split, reporting, optimization). The **Persistence Layer** stores versioned agent/workflow JSON under `meta/`, per-experiment `states.json`, and Markdown reports under `result/`.

**Fig. 1.** High-level architecture: Presentation Layer (visual editor), Service Layer (API, LangGraph, plugins), Persistence Layer (metadata, results, reports).

**Distributed inventory (release v2.x).** 47 pre-built agents (21 LLM, 26 PGM), 9 reusable subgraphs (`sg_`*), 19 reference workflows (`wf_*`), 12 tools, native parsers for **CDR**, **ChemDisGene**, and plain text.

---

## 2. Core features implementation

### Feature 1 — Automatic input inference (Algorithm S1)

Given a directed workflow graph G=(V,E) where each node declares inputs and outputs, NeuraGraph computes the minimal set of **global inputs** required to execute G, ensuring every data dependency is satisfied before run-time (see Algorithm S1 table).

### Feature 2 — Recursive subgraph composition (Algorithm S2)

Hierarchical pipelines are built with `**flowNodes` of kind `loop`**, each referencing a reusable subgraph file `sg_`* (e.g. sentence-level NER, pairwise relation verification). For each element of a list in shared state (`sentences`, `pairs`, …), the engine runs the loop body once and **merges** list/dict outputs into the parent state. This replaces legacy SUB-type controllers in release 1.0. Algorithm S2 summarizes the invocation pattern.

### Feature 3 — Plugin integration and sandbox execution

Local biomedical models (e.g. Flair/HunFlair2) are integrated through a unified `Plugin` base class whose `load()` method exposes named capabilities to programmatic agents and tools. Heavy dependencies run in **isolated sandbox sidecars**—separate local processes with dedicated virtual environments (`meta/plugins_sandbox.json`, default Flair sidecar on port 5002)—invoked by the main orchestrator via HTTP (`/health`, `/pgm/run`, `/tool/run`). Lightweight agents execute **in-process** under import-restricted PGM execution. Plugins are cached after first load. Custom models can be added via `sandbox/<id>/plugins_impl.py` or the ≤50-line `sandbox/_template` without Docker.

### Feature 4 — Batch experiments and reproducibility

Batch experiments are designed so a completed run can be audited and repeated under the same configuration. The platform stores the workflow that was executed, a snapshot of each agent and tool definition as it stood when the workflow was saved (so later edits in the visual editor do not change what an old experiment actually ran), and per-article logs of inputs, intermediate outputs, predictions, and evaluation metrics. Re-running or reviewing an experiment therefore uses the stored workflow and agent snapshots rather than whatever happens to be loaded in the editor at review time. LLM-based steps are inherently stochastic; repeats are comparable only when the same model, endpoint, and sampling settings are kept and recorded alongside the run.

### Feature 5 — Evaluation metrics

When gold annotations are provided, NeuraGraph computes precision (P), recall (R), and F1 at **micro-** and **macro-average** levels. For each instance i:

P_i=\frac{TP_i}{TP_i+FP_i},\quad R_i=\frac{TP_i}{TP_i+FN_i},\quad F1_i=\frac{2P_iR_i}{P_i+R_i}.

**Micro-averaged** metrics aggregate counts over all instances before computing ratios; **macro-averaged** metrics average per-instance P_i, R_i, F1_i. Relation tasks use article-level aggregation where appropriate to avoid pseudoreplication from sentence-level counting.

### Feature 6 — LLM-powered reporting and tuning-driven refinement

A four-step experiment wizard (Fig. S2) separates test and tuning splits and links batch evaluation, LLM reporting, and tuning-guided workflow updates without manual orchestration coding.

**Fig. S2.** A four-step experiment wizard.

**1. Configure.** Select a workflow, assign test and tuning splits, and preview samples to confirm columns and gold fields.

**2. Baseline test and report.** Batch-run the workflow on the test split; persist per-sample results in `states.json`. A reporting agent reads these artifacts and experiment metadata and writes a structured Markdown baseline report (micro/macro metric tables, FN/FP examples) using a configurable local or cloud LLM.

**3. Tuning and optimize.** Batch-run the workflow on the tuning split and generate a tuning-set diagnostic report. Fig. S3 provides an example of the LLM-powered report, illustrating quantitative metrics, false positive pattern analysis (e.g., over-generation from combination regimens), and actionable agent modification suggestions with expected impact estimates.

**Suggestion generation rules.** The report prompt enforces the following constraints on modification proposals:

- **Scope:** Only changes implementable by editing existing agent metadata or programmatic code; no external systems, ontologies, or services.
- **Implementation cost:** Prefer simpler changes first: editing an LLM prompt text, then adding a small programmatic check, then re-wiring the workflow graph, and only as a last resort switching which tool an agent uses.
- **Evidence-based:** Proposals must be grounded in per-sample error data from the experiment; no invented errors outside the provided examples.
- **No shortcuts:** No guards that use gold labels, entity-type gates, or character-position thresholds without semantic reasoning. No full-text keyword or causal-phrase filters (they zero recall).
- **No hardcoding:** No sample IDs, entity names, or fixed string patterns.

The wizard's optimize step passes that report to a second LLM agent—the refiner—which returns structured per-agent modification plans. Each plan specifies the target agent, the prompt rule to modify, and the replacement text. The refiner is constrained to propose only biomedical semantic edits to LLM prompt templates; it cannot modify programmatic (PGM) logic, negation guards, or keyword filters. It reads the full report—including per-sample FN/FP evidence—and autonomously decides which edits to attempt. The report's suggestions are diagnostic input, not a direct instruction set: the refiner may follow them, combine them, or pursue different edits altogether.

**Validating modification plans.** The refiner generates plans under these constraints: **prioritize FN fixes** (Condition strengthen over new Assumptions), **do not add new Assumptions** (only refine existing ones, and only when evidence shows they failed to fire), **prefer surgical refinements** (one Condition at a time, one clinical pattern), and **one plan = one testable hypothesis**. Each plan is then tested on the tuning split:

1. **Filter validation.** The plan is mechanically checked against the target agent's current prompt — plans referencing nonexistent rule numbers, duplicating existing content, or violating patching format are skipped.
2. **Surgical variant testing.** The workflow is duplicated, the modification is applied to the target agent's prompt, and the tuning split is re-run. Applying a modification clones the agent definition and edits its prompt template by removing, appending, or replacing numbered rules. Multiple phrasings of the same edit may be tested as separate rounds.
3. **Acceptance.** A modification is retained only if tuning macro-F1 strictly exceeds the tuning baseline. Accepted edits are frozen as new agent versions; rejected edits are discarded.
4. **Iteration.** Steps 1–3 repeat for each plan. Accepted edits accumulate, so later rounds build on the best changes so far. The final set of accepted edits defines the optimized workflow.

The number of tested plans is determined by the refiner's output, not by the number of suggestions in the report. This protocol ensures that only empirically validated changes reach the held-out test split.

**4. Optimized test.** Re-run the selected workflow on the test split; the UI compares baseline versus optimized precision, recall, and F1 and can display an optimized test report.

**Fig. S3.** Example of an LLM-powered evaluation report.

The report follows a three-section Markdown layout: **(1) Metrics** — micro/macro P/R/F1 tables, F1 distribution, TP/FP/FN totals, and effective agent version mapping; **(2) FN/FP Analysis** — narrative diagnosis of dominant error patterns with representative article excerpts; **(3) Modification Suggestions** — numbered per-agent edits with expected impact estimates and feasibility justification.

**Report styling in the UI.** Markdown is rendered into scrollable panels. Tables use striped styling. Per-sample F1 trend charts are inserted after the metrics heading when the sample count exceeds 20. Error composition charts (TP/FP/FN buckets) appear after the analysis heading. Suggestion sections highlight proposed additions and removals. Chart instances are scoped per panel to prevent cross-tab data reuse.

---

## 3. Illustrative examples

To address end-to-end system assessment on a realistic pharmacological task, we evaluate NeuraGraph on the **BioCreative V Chemical–Disease Relation (CDR)** corpus under a **pharmacovigilance-oriented use case**: mining **chemical-induced disease (CID)** assertions from biomedical abstracts. Sections 3.2–3.3 define NER and oracle-RE workflows (i.e., RE using gold-standard pre-annotated entities rather than predicted entities); section 3.4 describes the NER to RE chain. Section 3.5 reports frozen-workflow performance on the 500-article test split: Task A (NER), Task B (oracle RE, gold entities from CSV), Task C (E2E, predicted entities → RE). The experiment registry is listed in **Table S10**.

### 3.1 Dataset Preparation

The workflow was evaluated using the BioCreative V Chemical–Disease Relations (CDR) corpus, a benchmark dataset for biomedical named entity recognition. The relevant dataset statistics are summarized in **Table S1**.

**Table S1.** Statistics of the benchmark datasets used for evaluation.


| Dataset Name | # Test set | # Dev set | Entity Labels     | Relations               |
| ------------ | ---------- | --------- | ----------------- | ----------------------- |
| CDR          | 500        | 50        | Chemical, Disease | Chemical-Induce-Disease |


### 3.2 An End-to-End Workflow for NER

Three top-level agents and one compound loop implement sentence-level NER (Fig. S4, **Table S2**): LLM sentence splitting (`text_sentence_split`), a loop node (`ner_sentence_loop`) that iterates over sentences and runs HunFlair2 tagging on each sentence via the nested PGM agent `ner_flair_sent`, then PGM metric calculation (`eval_metrics`) on document-level merged entities. Gold labels are read from the CDR test CSV into workflow **START** as `expected_entities` (one-line map in Table S3).

**Fig. S4.** Agent and flow-node specifications for the sentence-level NER workflow.

**Table S2.** Agent and flow-node specifications for the sentence-level NER workflow.


| Name (agent / node id) | Type            | Description                                                                                          | Inputs                                                     | Outputs                  |
| ---------------------- | --------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------ |
| `text_sentence_split`  | LLM             | Split document text into a JSON array of sentences.                                                  | article text                                               | `sentences`              |
| `ner_sentence_loop`    | Loop            | Foreach element of `sentences`; invoke subgraph `sg_ner_flair_sent`; merge per-sentence entity lists | `sentences`, `labels`                                      | `entities`               |
| `ner_flair_sent`       | PGM (loop body) | HunFlair2 NER via Flair plugin (`flair` sandbox); one sentence per iteration                         | `sentence`, `labels`                                       | `predicted` / `entities` |
| `eval_metrics`         | PGM             | Entity-level precision, recall, and F1 (micro/macro via metrics plugin)                              | `predicted` / `entities`, `expected` / `expected_entities` | `metrics`                |


**Prompt S1 (`text_sentence_split`).**

System:

```
You are an English-text sentence splitter.
```

User:

```
Task: split the following biomedical abstract into complete sentences according to English grammar and punctuation.
Rules:
- Keep all content, including braces, do not remove or alter them.
- Output **only** a JSON array of strings, one sentence per element.
- Do **not** add any explanations or extra text.
- **Do not add any introductory sentences like "Here is the output..."

Biomedical abstract:
{text}
```

**Table S3** details the source code line counts of each node in the NER task implemented by NeuraGraph.

**Table S3.** Source code lines of NeuraGraph for NER task.


| Node                | Lines  |
| ------------------- | ------ |
| text_sentence_split | 0      |
| ner_flair_sent      | 24     |
| eval_metrics        | 11     |
| **Total**           | **35** |


**Table S4** presents the source code line counts of the Custom Python implementation for the same NER task, with a total of 361 lines of code.

**Table S4.** Source lines of Custom Python for NER task.


| File                            | Lines   |
| ------------------------------- | ------- |
| custom_python_ner               | 63      |
| data parser                     | 169     |
| Data loader                     | 53      |
| Performance metrics calculation | 76      |
| **Total**                       | **361** |


### 3.3 A Workflow for Chemical–Induced–Disease Relation Extraction

Three top-level agents and one compound loop implement oracle-entity CID–RE (Fig. S5, **Table S5**): MeSH-id deduplication, LLM hypernym filtering, Cartesian pair generation, and per-pair LLM verification in compound loop `**sg_cid_re_verify`**. Relation-level P/R/F1 are computed from workflow graph metrics—no separate metrics node. Gold relations are read from CSV as `gold_relations`.

**Fig. S5.** Agent and flow-node specifications for the CID–RE workflow.

**Table S5.** Agent specifications for the relation‑extraction workflow.


| Name (agent / node id)       | Type            | Description                                                            | Inputs                                                                   | Outputs                                                |
| ---------------------------- | --------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ |
| `e2e_entities_dedup_by_id`   | PGM             | Deduplicate oracle entities by MeSH id; keep shortest synonym per id   | `entities` (from CSV)                                                    | `filtered_entities`                                    |
| `e2e_hypernym_filter`        | LLM             | Contextual hypernym/modifier filter (Prompt S2)                        | `entities`, `text`                                                       | `filtered_entities`                                    |
| `cid_pair_generate`          | PGM             | Enumerate chemical–disease candidate pairs from filtered entities      | `filtered_entities`                                                      | `pairs`                                                |
| `cid_re_verify_loop`         | Loop            | `foreach` over `pairs`; subgraph `sg_cid_re_verify`; merge `relations` | `pairs`, `text`                                                          | `relations` (MeSH id lines)                            |
| `relation_verify_llm`        | LLM (loop body) | Binary verdict `$` = induces / `~` = does not induce (Prompt S3)       | `text`, `head`, `tail`                                                   | `result`                                               |
| `relation_result_to_id_pair` | PGM (loop body) | Emit `head_id                                                          | tail_id`when`$`; negation + associative guards (50-char negation window) | `result`, `head_id`, `tail_id`, `text`, `head`, `tail` |


**Table S6** details the source code line counts of each node in the RE task implemented by NeuraGraph. **Table S7** and **Table S8** compare Custom Python and Dify tool implementations for the same task.

**Table S6.** Source code lines of NeuraGraph for RE task.


| Node                       | Lines          |
| -------------------------- | -------------- |
| e2e_entities_dedup_by_id   | 20             |
| e2e_hypernym_filter        | 0 (LLM prompt) |
| cid_pair_generate          | 24             |
| relation_verify_llm        | 0 (LLM prompt) |
| relation_result_to_id_pair | 91             |
| **Total (PGM)**            | **135**        |


**Table S7.** Source code lines of Custom Python for RE task.


| File                            | Lines   |
| ------------------------------- | ------- |
| custom_python_re                | 68      |
| data parser                     | 169     |
| Data loader                     | 53      |
| Performance metrics calculation | 76      |
| **Total**                       | **366** |


**Table S8** provides the source code line counts of the Dify Tool for both NER and RE tasks, serving as an additional comparison benchmark.

**Table S8.** Source lines of Dify Tool for RE.


| File          | Lines |
| ------------- | ----- |
| Dify_tools_re | 232   |


**Prompt S2 (`e2e_hypernym_filter`).**

System:

```
You are a biomedical entity normalization expert. Do not call tools. Your reply must be ONLY the final JSON array — no reasoning, markdown, or prose.
```

User:

```
{text}
You are an expert of biomedical domain, above article is a biomedical paper.

Entities (JSON array of {{"text", "id", "label"}}):
{entities}

Step 1 — Drop standalone modifiers (before any pairwise comparison):
- Remove Disease rows whose text is ONLY a modifier token (temporal course, severity, stage, or similar qualifying adjective) with no disease head noun.
- Keep multi-word disease phrases even when they begin with such a modifier.
- Do not remove Chemical entities in this step.

Step 2 — Rules BEFORE pairwise hypernym removal:
1. Same id = same synonym cluster (upstream grouping). NEVER remove an entity based on comparison with another entity that has the SAME id.
2. Only compare pairs with DIFFERENT ids (same label).
3. Clinical near-synonyms or same disease event in this article: if two entities with different ids name the same condition/process, treat as '~' in BOTH orderings and KEEP both — do not remove either as a hypernym.
4. Do not remove a specific disease mention in favor of a bare modifier-only token.

Step 3 — For each pair (A,B) with the SAME label and DIFFERENT ids, substitute head and tail with the two entity texts:
1. different type → '~'
2. same type, head narrower than tail → '~'
3. same type, head broader than tail → '$'

Evaluate both (A,B) and (B,A). Remove an entity only if it receives '$' as head in comparison with another entity with a DIFFERENT id.

CRITICAL: Do NOT change or invent ids. Keep exact ids from input.

Output ONLY a JSON array:
[{{"text": "...", "id": "...", "label": "Chemical"|"Disease"}}]
```

**Prompt S3 (`relation_verify_llm` v0010).**

System:

```
You are a biomedical expert. Answer with '$' or '~' only. Do not output any other message.
```

User:

```
{text}
You are biomedical expert, refer to above biomedical article, please give answer '$' or '~' only
based on below rules. Apply all Assumptions first; if any assumption applies, answer '~' immediately and do not use Conditions.
Assumptions:
1.1 if 'patient had/exhibited {tail} on the Xth day of {head} treatment', please do not use it and find other reason.
1.2 if 'difference did not reach statistical significance compared to groups' appeared, please do not use it and find other reason.
1.3 if {head} appears only as a physiological/dietary state or experimental grouping (e.g. 'sodium depletion/repletion', 'volume depleted', 'fasted', 'control group') and not as a chemical administered to subjects, answer '~'.
1.4 if the only link between {head} and {tail} is inhibition/blockade/suppression of {head} or '{head} synthesis' by another drug (e.g. 'inhibition of {head} synthesis', 'another drug inhibits {head}'), and {tail} is attributed to that other drug or the inhibition mechanism—not to {head} itself as the causative agent—answer '~'.
1.5 if {head} is used as resuscitation, rescue therapy, antidote, or treatment for {tail} (or for local anaesthetic systemic toxicity / LAST) and {tail} is the condition being treated rather than caused by {head}, answer '~'.
Conditions:
1. if the article explicitly states that {head} caused or induced {tail} (e.g., '{head}-induced {tail}', '{head} caused {tail}', '{head} resulted in {tail}', '{head} led to {tail}'), answer '$'
2. else if the article states that the interaction between {head} and another chemical induces {tail}, answer '$'
3. else if {head} is administered together with other chemical(s) as a combination/co-treatment regimen and {tail} is reported as an adverse event, toxicity, or complication (including incidence or percentage) in patients receiving that regimen, answer '$' for {head} as a component of the regimen—even when the text attributes the event to the combination rather than {head} alone
4. else if the article mentions {tail} was reported in the percentage of patients because of {head}, and the article explicitly establishes causation (not merely listing adverse events), answer '$'
5. else if the article mentions '{head} is mediating/attenuating {tail}', answer '~'
6. else if {head} and {tail} have no relationship, answer '~'.
DO NOT output any other message.
```

### 3.4 An end-to-end workflow for NER to RE

The sentence-level NER pipeline from §3.2 is chained into the CID–RE pipeline from §3.3 to form an end-to-end workflow (Fig. S6, **Table S9**): predicted NER entities pass through synonym clustering and alias snapshot, then flow into entity deduplication, hypernym filtering, pair generation, and per-pair verification, with PGM relation-level metric calculation. Unlike oracle-entity RE in §3.3, no pre-annotated entities are provided—only `text`, `labels`, and `gold_relations` are read from CSV, so NER errors propagate into pair generation and verification.

**Fig. S6.** An end-to-end workflow for NER to RE.

**Table S9.** Agent, subgraph, and node specifications for the E2E NER→RE workflow. Subgraphs reused from §3.2–3.3 reference their source tables; only E2E-specific nodes are described in full.


| Name (agent / subgraph / node id) | Type     | Description                                                                            | Inputs                          | Outputs                 |
| --------------------------------- | -------- | -------------------------------------------------------------------------------------- | ------------------------------- | ----------------------- |
| `sg_ner_flair_sent`               | Subgraph | Refer to Table S2                                                                      | `text`, `labels`                | `entities` (label dict) |
| `ner_entities_to_re_format`       | PGM      | Convert Flair label dict to entity list format `[{text, label, id}]`                   | `entities`                      | `entities` (list)       |
| `e2e_entities_passthrough`        | PGM      | Deduplicate Flair NER entities; use surface text as id when MeSH id is missing         | `entities`                      | `filtered_entities`     |
| `e2e_synonym_filter`              | LLM      | Assign entities to synonym clusters (shared id); do not drop entities (Prompt S4)      | `entities`, `text`              | `filtered_entities`     |
| `e2e_entities_assign_group_ids`   | PGM      | Assign shared numeric group ids (1, 2, …) per label to synonym groups                  | `entities`, `filtered_entities` | `filtered_entities`     |
| `e2e_entity_aliases_snapshot`     | PGM      | Preserve all synonym surface forms + group ids for metrics lookup (before dedup)       | `filtered_entities`             | `entity_aliases`        |
| `sg_cid_re_verify`                | Subgraph | Refer to Table S5                                                                      | `filtered_entities`, `text`, …  | `relations`             |
| `eval_metrics_relation`           | PGM      | Normalize surface forms via alias map; compare predicted relations to `gold_relations` | `relations`, `ground_truth`, …  | `metrics`               |


**Prompt S4 (`e2e_synonym_filter`).**

System:

```
You are a biomedical entity normalization expert. Do not call tools. Your reply must be ONLY the final JSON array — no reasoning, markdown, or prose.
```

User:

```
Text:
{text}

Entities (JSON array of {{"text", "id", "label"}}):
{entities}

Task: assign each input entity to a synonym CLUSTER. Grouping only — do NOT drop any entity.

A cluster = entities that would map to the same MeSH concept in BC5CDR (same chemical, or same disease), based on this article.

Same label + same cluster id when:
- Abbreviation, generic name, or trade name of the same drug/substance.
- Morphological variant of the same drug (e.g. -related, -associated, -induced).
- Clinical near-synonyms for the SAME disease event or pathological process in context: e.g. organ injury, organ toxicity, organ inflammation, organ damage, or named syndrome wording that refers to one outcome.
- One drug-adverse-event narrative in the article → one Disease cluster id for all Disease mentions describing that same reaction (do not split injury vs toxicity vs inflammation vs named disease if they refer to one event).
- Multi-word disease phrase and its head term → same cluster.
- Bare temporal/severity/course modifier alone → same cluster id as the disease phrase it modifies in the text, not a separate cluster.

Different cluster ids only when the article clearly denotes distinct chemicals, or distinct unrelated disease conditions/events.

Output — ONE row per INPUT entity (count must match input):
- text = exact input surface form (preserve casing).
- id = cluster key shared by all cluster members (stable canonical phrase from the group; no MeSH/CHEBI/DOID codes).
- label = Chemical or Disease.

CRITICAL:
- Every input entity exactly once; do NOT omit entities.
- All members of one cluster use the identical id string.
- Do not invent ontology codes.

Output ONLY a JSON array:
[{{"text": "...", "id": "...", "label": "Chemical"|"Disease"}}]
```

### 3.5 Full performance evaluation (pharmacovigilance use case)

#### 3.5.1 Use case

Given PubMed-style title+abstract text, the system (1) tags **Chemical** and **Disease** mentions, (2) verifies which chemical–disease pairs are supported as CID (chemical **induces** disease) in context, and (3) logs micro/macro precision, recall, and F1 with per-article experiment logs for audit.

#### 3.5.2 Evaluation protocol

1. **NER (Task A).** Run Flair NER (§3.2) and LLM NER on 500 test data. Metrics: entity-level micro/macro P/R/F1.
2. **CID–RE (Task B).** Run LLM RE (§3.3) with gold entities in data. Report baseline workflow and optimized workflow (tuned by dev data).
3. **CID–RE, end-to-end (Task C).** Run NER (Task A), then run the optimized CID workflow (Task B) and compare with end-to-end workflow built by PubTator3 API.

The experiment registry is listed in **Table S10**.

**Table S10.** Experiment registry (BC5CDR test 500). Sub-experiments for Task B are nested under parent `678a855f`; in the UI, open **[http://127.0.0.1:5001/exp/678a855f-1f8a-492e-9d39-be37df122795](http://127.0.0.1:5001/exp/678a855f-1f8a-492e-9d39-be37df122795)** → wizard **Tab 3 (Tuning & Optimize)** to view tuning baseline report, accepted refinement metrics, and optimize-loop summary.


| Task | Method                          | Runner / script              | Dataset  | Experiment id                          |
| ---- | ------------------------------- | ---------------------------- | -------- | -------------------------------------- |
| A    | Flair NER                       | `wf_doc_ner_flair_sent_eval` | 500 test | `064f47ac-2d08-4e9a-85e3-2ca2e564c7da` |
| A    | LLM NER1                        | `wf_doc_ner_llm_eval`        | 500 test | `aba808f2-46ad-4585-984f-633955729315` |
| B    | LLM RE (baseline)               | `wf_cid_re_llm_linear`       | 500 test | `678a855f-1f8a-492e-9d39-be37df122795` |
| B    | LLM RE (tuning baseline)        | `wf_cid_re_llm_linear`       | 50 dev   | `opt_base_tune_81781d50`               |
| B    | LLM RE (accepted refinement)    | `wf_cid_re_llm_linear`       | 50 dev   | `opt_cand_ddi_c2_8cb2b66e`             |
| B    | LLM RE (optimized)              | `wf_cid_re_llm_linear_opt_`* | 500 test | `opt_best_20260609_131256_d388be08`    |
| C    | E2E (Flair NER to optimized RE) | `wf_e2e_flair_opt_re`        | 500 test | `bffea244-c3dd-4b97-98f2-9ed4d7bb895a` |
| C    | E2E (PubTator3)2                | `wf_e2e_pubtator_re`         | 500 test | `5c3bad58-a7ea-4236-ae95-e8956b736e7e` |


1 `wf_doc_ner_llm_eval` replaces the Flair sentence loop with a single document-level LLM NER call, serving as an LLM-only NER baseline for comparison with the hybrid Flair pipeline.

2 `wf_e2e_pubtator_re` composes subgraph `sg_e2e_pubtator_re` (PubTator3 API for NER + RE) with the same `eval_metrics_relation` node, providing an external E2E baseline against LLM RE.

#### 3.5.4 Experiment Results

**Task A.** Two NER workflows were evaluated on the 500-article BC5CDR test split (Table S11). The hybrid Flair pipeline (`wf_doc_ner_flair_sent_eval`) achieved micro-F1 0.779 and macro-F1 0.779, outperforming the LLM-only approach (`wf_doc_ner_llm_eval`, micro-F1 0.656 / macro-F1 0.667). The Flair model benefits from per-sentence biomedical token classification; the LLM approach, while end-to-end, suffers from hallucinated spans and missed multi-token entities at document scale.

**Table S11.** Task A: NER on BC5CDR test (n=500). Entity-level metrics.


| Method    | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 |
| --------- | ------- | ------- | -------- | ------- | ------- | -------- |
| Flair NER | 0.725   | 0.840   | 0.779    | 0.737   | 0.844   | 0.779    |
| LLM NER   | 0.640   | 0.673   | 0.656    | 0.672   | 0.690   | 0.667    |


*Table S11 (Flair row): batch run on `cdr_test_500.csv` (experiment `064f47ac-2d08-4e9a-85e3-2ca2e564c7da`, completed 2026-06-03). Micro: aggregate TP/FP/FN over 500 articles; macro: mean of per-article P/R/F1.*

*Table S11 (LLM row): `scripts/run_perf_ner_test500.py --runner wf_doc_ner_llm_eval` (experiment `aba808f2-46ad-4585-984f-633955729315`, completed 2026-06-04). Same metric protocol as Flair row.*

**Task B.** Pharmacovigilance CID–RE was tuned on a **stratified 50-article** subset of CDR `dev.txt` via the experiment wizard (Feature 6, §2).

**1. Baseline.** The baseline workflow `wf_cid_re_llm_linear` (§3.3, Table S5) was batch-run on the 500-article test split and the 50-article dev tuning split. The tuning baseline (v0010) achieved macro-F1 0.642 on dev.

**2. Report.** `report_experiment` (Prompt S5) generated a tuning-set diagnostic report following the Fig. S3 layout (§2, Feature 6). The report identified 47 FNs (e.g., sample 12 cisapride–diltiazem QT prolongation, Condition 2 not matched; sample 24 ifosfamide toxicity list) and 101 FPs (e.g., sample 33 diazepam as treatment; sample 15 angiotensin as physiological substance; sample 7 creatinine as lab marker), and proposed four modification suggestions:

**S1: Physiological substances & lab markers.** Target: `relation_verify_llm` (v0010). Add a new Assumption 1.6: reject endogenous/lab substances (creatinine, angiotensin, serotonin, etc.) as `{head}` unless explicitly administered as drugs. Impact: 15–25 FP reduction (samples 7, 15, 16, 33, 5).

**S2: Treatment/rescue drug detection.** Target: `relation_verify_llm` (v0010). Expand Assumption 1.5 to include sedatives and supportive care (diazepam, morphine, naloxone) — answer '~' when `{head}` treats any condition in the article. Impact: 10–15 FP reduction (samples 33, 44).

**S3: PGM negation guard in relation_result_to_id_pair.** Target: `relation_result_to_id_pair` (v0003). Require negation phrases within 30 chars of both head AND tail, not just one. Impact: 3–5 FN reduction (sample 6, ifosfamide–emesis).

**S4: Combination therapy adverse events.** Target: `relation_verify_llm` (v0010). Clarify Condition 3: when `{head}` is part of a multi-drug regimen and `{tail}` is an adverse event in the study population, answer '$' even if attributed to the combination. Impact: 5–8 FN reduction (samples 12, 24).

**3. Refiner.** `agent_refiner` (Prompt S6) reads the full report and produces modification plans. **S1** and **S3** were filtered out: S1 proposes a new Assumption, which the refiner prompt disallows ("Do not add new Assumptions"); S3 targets a programmatic agent, which the refiner cannot edit. **S2** and **S4** passed and became two test rounds (**Table S12**):

- **Round 1 (S2)** — expanded Assumption 1.5 for sedatives/supportive care. Rejected: macro-F1 fell to 0.605 (Δ −0.036).
- **Round 2 (S4)** — clarified Condition 2 for combination therapy and reversed-order DDI phrasing. Accepted: macro-F1 rose to 0.666 (Δ **+0.024**).

**Refiner prompt change.** The accepted modification refined **Condition 2** in `relation_verify_llm` to capture reversed-order drug–drug interaction phrasing. Before (v0010): *"else if the article states that the interaction between {head} and another chemical induces {tail}, answer '$'"*. After (v0013): *"else if the article describes a drug–drug or drug–chemical interaction involving {head} that causes or contributes to {tail} (e.g. '{head}-{other drug} interaction', '{other drug}-{head} interaction', 'interaction between {head} and', 'co-administration of {head}'), answer '$'"*. This addresses sample 12 where "cisapride–diltiazem interaction" uses reversed head–other ordering.

**4. Optimize.** The accepted change was frozen as `relation_verify_llm` v0013. The optimized workflow `wf_cid_re_llm_linear_opt_`* was re-run on the 500-article test split (**Table S13**).

**Table S12.** Dev50 tuning — baseline and accepted refinement (oracle entities, n=50).


| Stage                   | Experiment id                    | Macro-F1 | ΔMacro-F1 |
| ----------------------- | -------------------------------- | -------- | --------- |
| Tuning baseline (v0010) | `opt_base_tune_81781d50`         | 0.642    | —         |
| Round 1 — toxidrome15   | `opt_cand_toxidrome_15_420244af` | 0.605    | −0.036    |
| Round 2 — ddic2 (v0013) | `opt_cand_ddi_c2_8cb2b66e`       | 0.666    | +0.024    |


*Table S12: Sub-experiments nested under parent `678a855f` (Table S10). Round 1 was rejected; Round 2 passed and was frozen as v0013.*

**Table S13.** Task B: CID relation extraction on BC5CDR test (n=500) — oracle entities. Relation type: Chemical-induces-Disease (MeSH id pairs).


| Method                                                  | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 |
| ------------------------------------------------------- | ------- | ------- | -------- | ------- | ------- | -------- |
| LLM RE (baseline, `wf_cid_re_llm_linear`, v0010)        | 0.583   | 0.750   | 0.656    | 0.610   | 0.757   | 0.642    |
| LLM RE (optimized, `wf_cid_re_llm_linear_opt_`*, v0013) | 0.603   | 0.761   | 0.673    | 0.626   | 0.791   | 0.666    |


*Table S13: Baseline exp `678a855f` (`relation_verify_llm` v0010). Optimized (dev50 wizard, v0013): exp `opt_best_20260609_131256_d388be08`.*

**Task C.** The end-to-end pipeline chains Flair NER predictions from Task A into the optimized CID–RE workflow from Task B (§3.4, Table S9). Unlike Tasks A–B, no pre-annotated entities are provided—only `text`, `labels`, and `gold_relations` are read from CSV, so NER errors propagate into pair generation and verification. The PubTator3 API baseline (`wf_e2e_pubtator_re`) provides an external comparison. NeuraGraph E2E achieved micro-F1 0.635 (macro 0.663), substantially outperforming PubTator3 (micro 0.394, macro 0.422). The dominant error source is NER recall (0.840 vs PubTator3's lower entity recall), which compounds into missed relation pairs downstream.

**Table S14.** Task C: CID relation extraction on BC5CDR test (n=500) — end-to-end.


| Method                         | Micro-P | Micro-R | Micro-F1 | Macro-P | Macro-R | Macro-F1 |
| ------------------------------ | ------- | ------- | -------- | ------- | ------- | -------- |
| E2E (Flair NER → optimized RE) | 0.543   | 0.765   | 0.635    | 0.632   | 0.781   | 0.663    |
| E2E (PubTator3)                | 0.281   | 0.660   | 0.394    | 0.344   | 0.699   | 0.422    |


*Table S15 (Flair→RE row, n=500): merged experiment `bffea244-c3dd-4b97-98f2-9ed4d7bb895a` (`scripts/merge_e2e_states.py --500` on `cdr_test_500.csv`). Workflow `wf_e2e_flair_opt_re` (§3.4, Table S9). Micro: TP=724, FP=609, FN=223.*

*Table S15 (PubTator3 row, n=500): experiment `5c3bad58-a7ea-4236-ae95-e8956b736e7e` (`wf_e2e_pubtator_re`, completed 2026-06-10). Micro: TP=668, FP=1708, FN=344.*

## 4. Pre-built component inventory

The distribution includes **67** agents (**36** LLM, **31** PGM), **33** graphs (**10** subgraphs, **23** workflows), **12** callable tools, and **3** native dataset parsers (CDR, ChemDisGene, plain text). Component ids match files under `meta/agents/`, `meta/graphs/`, and `meta/tools/` (workflow optimization copies with `_opt_YYYYMMDD` timestamps and auto-generated `ner_flair_sent_loop` are excluded from the workflow count).

**Agent and graph inventory (Tables S15–S18):** [META_INVENTORY.md](META_INVENTORY.md) — regenerate with `python scripts/gen_meta_inventory.py`.

**Tools** (`meta/tools/`, 12 entries) and **dataset parsers** (`parser_cdr`, `parser_chemdisgene`, `parser_plain_text`) are documented in [DATA_FORMAT.md](DATA_FORMAT.md). CSV builders use `DatasetCatalog` in `plugin/plugins.py`.