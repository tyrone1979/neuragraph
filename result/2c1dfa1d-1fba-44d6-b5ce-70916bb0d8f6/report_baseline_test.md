## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| TP | 0 |
| FP | 0 |
| FN | 2 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |

**Error Totals:** 2 FN, 0 FP across 2 samples.

## 2) FN and FP Analysis

**Sample 1 — FN: "Aspirin may reduce the risk of heart disease."**
- **Gold relation:** Aspirin (Chemical) → heart disease (Disease) — causal/risk reduction context.
- **Pipeline output:** `filtered_entities` is empty (`[]`), so no pairs were generated.
- **Root cause:** The `e2e_hypernym_filter` LLM agent removed all entities. The input entities list contains only Phenobarbital/dyskinesia/movement disorders entities (from a different article context), which are irrelevant to the actual text "Aspirin may reduce the risk of heart disease." The hypernym filter likely dropped these mismatched entities, but the upstream entity extraction step failed to produce correct entities for this text. The pipeline never reached the relation verification stage.

**Sample 2 — FN: "Metformin is commonly used to treat type 2 diabetes."**
- **Gold relation:** Metformin (Chemical) → type 2 diabetes (Disease) — treatment context (should be negative/`~`).
- **Pipeline output:** `result = '~'` — correctly identified as non-causal.
- **Issue:** The gold standard expects this to be a positive CID relation, but the text describes treatment, not causation. This is a gold data quality issue, not a pipeline error. The pipeline correctly rejected this pair.

**Summary:** The primary pipeline failure is in Sample 1, where entity extraction upstream of the graph produced entities from a different article, causing the hypernym filter to drop everything and preventing any relation verification.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix entity extraction context mismatch
- **Target agent:** `e2e_hypernym_filter`
- **What to change:** Add a guard in the PGM process (not the LLM prompt) that checks if the input `entities` list contains any entity whose text appears in the input `text`. If zero entities match the text, pass all entities through unchanged.
- **Expected impact:** Prevents the hypernym filter from dropping all entities when upstream entity extraction produces entities from a different article context. This would allow Sample 1 to proceed to pair generation and relation verification.
- **Why easy:** Simple PGM guard added to the existing agent process — no new tools or external dependencies.

### Suggestion 2: Improve entity-text alignment in pair generation
- **Target agent:** `cid_pair_generate`
- **What to change:** Before generating pairs, filter entities to only those whose text appears in the input `text` (case-insensitive substring match). Add a PGM guard: `if txt.lower() not in text.lower(): continue`.
- **Expected impact:** Prevents generation of pairs from entities that don't belong to the current article text, reducing noise and ensuring only relevant Chemical-Disease pairs are verified.
- **Why easy:** Single-line PGM addition to the existing process — no new tools or external dependencies.