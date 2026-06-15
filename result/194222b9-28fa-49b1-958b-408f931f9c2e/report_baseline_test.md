## 1) Metrics

**Experiment Overview**
- **Experiment ID:** 194222b9-28fa-49b1-958b-408f931f9c2e
- **Graph:** sg_e2e_cid_re (E2E CID RE subgraph)
- **Dataset:** regression_2_gold_test.csv (2 samples)
- **Report Mode:** table (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| e2e_entities_passthrough | current |
| e2e_synonym_filter | current |
| e2e_entities_assign_group_ids | current |
| e2e_entity_aliases_snapshot | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |
| cid_pair_generate | current |
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |

**Per-Sample Results**

| Sample ID | Text | Pairs Generated | Result | Notes |
|---|---|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin → heart disease) | $ (induce) | False Positive: Aspirin reduces risk, does not induce |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | N/A | No Disease entity extracted; no pairs generated |

**Overall Metrics**
- **Total Samples:** 2
- **Pairs Generated:** 1 (sample 1)
- **Correct Pairs:** 0
- **False Positives:** 1 (sample 1)
- **False Negatives:** 1 (sample 2, missing Disease entity)
- **Precision:** 0.0
- **Recall:** 0.0
- **F1:** 0.0

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**
- **Text:** "Aspirin may reduce the risk of heart disease."
- **Entities:** Aspirin (Chemical, id=1), heart disease (Disease, id=1)
- **Pair:** Aspirin → heart disease
- **LLM Verdict:** $ (induce)
- **Cause:** The `relation_verify_llm` prompt (v0010) does not have a rule to handle preventive/reductive relationships. Condition 4 ("article mentions {tail} was reported in the percentage of patients because of {head}") and Condition 1 ("{head} caused or induced {tail}") are too broad. The phrase "may reduce the risk of" is a preventive relationship, not causative. The LLM incorrectly interprets "reduce the risk of" as a causal link rather than a protective one. The `relation_result_to_id_pair` PGM's negation guard does not catch this because "reduce the risk of" is not in the negation_phrases list.

**False Negative Analysis (Sample 2)**
- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **Entities Extracted:** Metformin (Chemical, id=1) only
- **Missing Entity:** "type 2 diabetes" (Disease)
- **Cause:** The upstream NER pipeline (not shown in this package) failed to extract "type 2 diabetes" as a Disease entity. Since no Disease entity is present, `cid_pair_generate` produces zero pairs, and no relation verification occurs. This is an entity extraction failure, not a relation verification issue.

## 3) Agent Modification Suggestions

### Suggestion 1: Add preventive/reductive relationship rule to relation_verify_llm prompt

- **Target Agent:** `relation_verify_llm` (v0010)
- **What to Change:** Add a new Assumption rule (1.6) to the prompt template's human section, before Conditions.
- **Change:** Insert after assumption 1.5: `"1.6 if the article states that {head} prevents, reduces risk of, protects against, or treats {tail} (e.g., '{head} reduces risk of {tail}', '{head} prevents {tail}', '{head} protects against {tail}', '{head} is used to treat {tail}'), answer '~'."`
- **Expected Impact:** Eliminates the FP in sample 1 (Aspirin → heart disease) and similar preventive/reductive relationships across all samples.
- **Why Easy:** Single prompt template edit; no code changes, no new tools, no external dependencies. Follows the existing Assumption pattern (1.1–1.5).

### Suggestion 2: Add "reduce risk" to negation guard in relation_result_to_id_pair

- **Target Agent:** `relation_result_to_id_pair` (v0003)
- **What to Change:** Add `'reduce risk of'`, `'reduces risk of'`, `'reduced risk of'`, `'prevent'`, `'prevents'`, `'prevented'`, `'protect against'`, `'protects against'`, `'protected against'` to the `negation_phrases` list in the PGM process.
- **Expected Impact:** Provides a second layer of defense for preventive/reductive relationships, catching cases where the LLM prompt change might not apply (e.g., edge cases with different phrasing).
- **Why Easy:** Simple list addition in existing PGM code; no new logic or dependencies. Complements Suggestion 1.

### Suggestion 3: Improve Disease entity extraction for common disease names

- **Target Agent:** Upstream NER pipeline (not in this package, but referenced via `entities` input)
- **What to Change:** This is outside the scope of the current graph agents. However, within the graph, the `e2e_synonym_filter` could be enhanced to detect missing Disease entities by analyzing the text for common disease patterns.
- **Change:** Add a PGM guard after `e2e_entities_passthrough` that scans the text for common disease-indicative phrases (e.g., "type 2 diabetes", "heart disease", "cancer") and injects them as Disease entities if not already present. This guard would use a small set of regex patterns for common disease constructions.
- **Expected Impact:** Reduces FN from missing Disease entities (like sample 2).
- **Why Easy:** New PGM node inserted between `e2e_entities_passthrough` and `e2e_synonym_filter`; no LLM calls, no external APIs. Uses simple string matching on the input text.