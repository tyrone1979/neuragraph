# Experiment Report: wf_kg_flair_full_regression_2_gold_test.csv_20260615093344

## 1) Metrics

| Metric | Value |
|--------|-------|
| Experiment ID | 77cbafbb-f164-4ced-b505-89d18d7db67c |
| Graph | wf_kg_flair_full |
| Dataset | regression_2_gold_test.csv |
| Sample Count | 2 |
| Report Mode | table |
| Status | completed |

**Agent Version Mapping (authoritative: agent_versions.effective)**

| Agent ID | Version Used |
|----------|-------------|
| ner_flair_doc | current |
| ontology_entity_link | current |
| kg_triple_extract_llm | current |
| kg_triple_merge | current |
| kg_rdf_export | current |

**Per-Sample Metrics**

| Sample ID | Text | Gold Entities |
|-----------|------|---------------|
| 1 | Aspirin may reduce the risk of heart disease. | Chemical: [Aspirin], Disease: [heart disease] |
| 2 | Metformin is commonly used to treat type 2 diabetes. | Chemical: [Metformin], Disease: [type 2 diabetes] |

**Note:** No metrics_summary or eval_metrics_relation data was provided in the experiment package. The states contain only entity-level gold data with no relation-level gold annotations or pipeline output for comparison. The experiment completed without errors but no evaluation metrics (precision, recall, F1) were computed.

## 2) FN and FP Analysis

**False Negative Analysis:**
- No explicit FN/FP data is available in the provided states. The states contain only input text and gold entity annotations (Chemical, Disease) for 2 samples.
- The pipeline output (entities from ner_flair_doc, triples from kg_triple_extract_llm, etc.) is not captured in the states, preventing direct FN/FP analysis.
- Based on the gold entities provided:
  - Sample 1: "Aspirin" (Chemical), "heart disease" (Disease)
  - Sample 2: "Metformin" (Chemical), "type 2 diabetes" (Disease)
- The Flair NER agent (ner_flair_doc) uses HunFlair2 model which should recognize these common biomedical entities. Any FN would likely stem from the NER step failing to detect these mentions.

**False Positive Analysis:**
- No pipeline output is available to identify false positives.
- The triple extraction step (kg_triple_extract_llm) could potentially generate spurious relations if the LLM hallucinates predicates or entities not present in the text.

**Likely Causes:**
1. **NER Misses:** HunFlair2 may fail on certain surface forms (e.g., "heart disease" vs "cardiovascular disease") or miss entities in complex sentence structures.
2. **Entity Linking Errors:** The ontology_entity_link LLM may map mentions to incorrect canonical forms, causing downstream triple mismatches.
3. **Triple Extraction Overgeneration:** The kg_triple_extract_llm prompt may produce triples with predicates not supported by the gold standard or entities not in the provided list.

## 3) Agent Modification Suggestions

### Suggestion 1: Improve Triple Extraction Predicate Normalization
- **Target Agent:** kg_triple_extract_llm
- **What to Change:** Modify the prompt template's human message to include a constrained predicate list and explicit instruction to only use entities from the provided list.
- **Expected Impact:** Reduces FP triples with hallucinated predicates or entities. Improves alignment with gold relation schemas.
- **Why Easy:** Single prompt edit in agent meta; no code changes needed.

### Suggestion 2: Add Entity Validation in Triple Merge
- **Target Agent:** kg_triple_merge
- **What to Change:** Add a PGM guard that checks if head/tail entities appear in the original entities list from ner_flair_doc before including the triple.
- **Expected Impact:** Eliminates triples containing entities not detected by NER, reducing FP from LLM hallucination.
- **Why Easy:** Small PGM code addition; uses existing graph binding (entities from ner_flair_doc is already available in the graph flow).

### Suggestion 3: Strengthen NER Deduplication
- **Target Agent:** ner_flair_doc
- **What to Change:** Add case-insensitive deduplication in the seen set logic (e.g., `span.text.lower()` instead of `span.text`).
- **Expected Impact:** Reduces duplicate entity mentions that differ only in casing, improving downstream triple quality.
- **Why Easy:** Single-line change in PGM process code.