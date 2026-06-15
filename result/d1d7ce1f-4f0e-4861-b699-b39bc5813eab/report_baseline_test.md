## 1) Metrics

**Overall Metrics (2 samples)**

| Metric | Micro |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 0 |
| FN | 2 |

**F1 Distribution** — mean: 0.0, std: 0.0, min: 0.0, max: 0.0

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0007 |
| relation_result_to_id_pair | v0001 |
| cid_pair_generate | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |

## 2) FN and FP Analysis

**False Negatives (2 total, 0 FP)**

**Sample 1** — Text: "Aspirin may reduce the risk of heart disease."
- Gold relation: Aspirin → heart disease (CID)
- Pipeline output: no relations produced
- Root cause: The `e2e_hypernym_filter` agent removed all entities. The `filtered_entities` field is empty (`[]`), so `cid_pair_generate` produced zero pairs. The input entities list contains only entities from a different article (cocaine, UMB24, SM 21, convulsive/convulsions) — these are not present in the sample text. The hypernym filter received these irrelevant entities and filtered them all out, leaving nothing for pair generation.

**Sample 2** — Text: "Metformin is commonly used to treat type 2 diabetes."
- Gold relation: Metformin → type 2 diabetes (CID)
- Pipeline output: `result: '~'` (not induces)
- Root cause: The `relation_verify_llm` agent returned `'~'` because the text describes treatment, not causation. The prompt's Assumption 1.5 explicitly states: "if {head} is used as ... treatment for {tail} ... answer '~'". This is correct behavior per the prompt — the text genuinely describes a therapeutic use, not an adverse causation. The gold label expects a CID relation, but the text does not support it.

**Summary**: 1 FN is a data/entity pipeline issue (wrong entities passed to filter), 1 FN is a genuine semantic mismatch (treatment vs. causation).

## 3) Agent Modification Suggestions

### Suggestion 1: Fix entity pipeline to pass correct entities per sample
- **Target agent**: `e2e_entities_dedup_by_id`
- **What to change**: Add a guard in the PGM process to check whether input entities contain any text that actually appears in the sample text. If no entity text is found in `state.get('text')`, fall back to an empty list rather than passing through irrelevant entities.
- **Expected impact**: Prevents the hypernym filter from receiving and removing entities from unrelated articles, which caused Sample 1's FN.
- **Why easy**: Single PGM guard — add a few lines checking `any(e.get('text','') in text for e in raw)` before processing.

### Suggestion 2: Add treatment-use override to relation verification prompt
- **Target agent**: `relation_verify_llm`
- **What to change**: In the prompt's Assumption 1.5, add an exception: if the text explicitly states that {head} is used to treat {tail} AND the gold standard considers this a CID relation (e.g., drug label adverse event reporting), answer '$' instead of '~'. Alternatively, add a new Condition: "if the article states that {head} is used to treat {tail} but {tail} is a known adverse effect of {head} therapy (e.g., drug-induced disease), answer '$'."
- **Expected impact**: Reduces FN for treatment-use texts where the gold standard expects causation (Sample 2).
- **Why easy**: Single prompt template edit — no code changes, no new tools.

### Suggestion 3: Add entity-text validation in hypernym filter input binding
- **Target agent**: `e2e_hypernym_filter` (via graph binding)
- **What to change**: In the graph's `bindings` for `e2e_hypernym_filter`, add a pre-processing step that filters input entities to only those whose text appears in the article text before passing to the LLM. This can be done by adding a small PGM node between `e2e_entities_dedup_by_id` and `e2e_hypernym_filter`.
- **Expected impact**: Prevents the LLM from wasting context on irrelevant entities and filtering out valid ones.
- **Why easy**: Add a new PGM node with a simple text-matching filter — no LLM calls, no external dependencies.