## 1) Metrics

**Experiment Overview**
- **Experiment ID:** f2c2dc1a-f157-43bf-a972-95b74cc148f2
- **Graph:** sg_e2e_cid_re (E2E CID RE subgraph)
- **Test Dataset:** regression_2_no_gold_test.csv (2 samples)
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

| Sample ID | Text | Pairs Generated | Result |
|---|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin → heart disease) | `$` (induced) |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | No pairs generated |

**Observations:**
- Sample 1 produced a false positive: "Aspirin may reduce the risk of heart disease" was classified as `$` (induces), but the text describes a protective/reducing effect, not causation.
- Sample 2 produced no pairs because only a Chemical entity (Metformin) was present; no Disease entity was extracted.

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**

- **Text:** "Aspirin may reduce the risk of heart disease."
- **Predicted Relation:** Aspirin induces heart disease (`$`)
- **Cause:** The `relation_verify_llm` agent (v0010) incorrectly classified this as `$`. The prompt's Condition 4 ("if the article mentions {tail} was reported in the percentage of patients because of {head}") does not apply. The text describes a *reduction* in risk, which is the opposite of causation. The LLM likely matched the surface pattern "head ... tail" without properly evaluating the semantic direction (reduce vs. cause).
- **PGM Guard Failure:** The `relation_result_to_id_pair` agent's negation guard did not catch this. The phrase "reduce the risk of" is not in the negation_phrases list, and the causal override logic found no explicit causal language, but the associative guard's distance threshold (15 chars) was not triggered because "associated with" etc. are absent.

**False Negative Analysis (Sample 2)**

- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **Predicted Relations:** None
- **Cause:** The `e2e_hypernym_filter` or upstream entity extraction failed to produce a Disease entity. The text contains "type 2 diabetes" which should be a Disease entity. The `filtered_entities` only contains Metformin (Chemical). This suggests the upstream NER or synonym/hypernym filtering dropped the Disease entity.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix False Positive on Protective/Reducing Language

**Target Agent:** `relation_verify_llm` (v0010)

**What to Change:** Add a new Assumption to the prompt (before Conditions) that explicitly handles protective/reducing/preventive language.

**Change Details:**
- Add Assumption 1.6: "If the text states that {head} reduces, prevents, protects against, lowers the risk of, or treats {tail}, answer '~' immediately."
- Insert after Assumption 1.5 and before Conditions.

**Expected Impact:** Eliminates false positives where the LLM misinterprets protective effects as causal induction. This is the most common error pattern in CID extraction (prevention vs. causation).

**Why Easy:** Single prompt line addition; no code changes, no new tools, no external dependencies. The pattern is semantically clear and does not require keyword matching.

---

### Suggestion 2: Improve Disease Entity Retention in Hypernym Filter

**Target Agent:** `e2e_hypernym_filter` (current)

**What to Change:** Add a guard in the prompt's Step 1 to explicitly retain disease entities that are specific medical conditions (e.g., named diseases, syndromes, disorders) even if they appear to be modifiers in some contexts.

**Change Details:**
- In Step 1, after "Remove Disease rows whose text is ONLY a modifier token...", add: "Exception: do NOT remove Disease rows that are recognized medical conditions (e.g., diabetes, hypertension, cancer, hepatitis, etc.) even if they appear to be standalone."
- Alternatively, rephrase Step 1 to: "Remove Disease rows whose text is ONLY a modifier token (temporal course, severity, stage, or similar qualifying adjective) with no disease head noun. Keep all rows that name a specific disease, condition, or syndrome."

**Expected Impact:** Prevents loss of Disease entities like "type 2 diabetes" in Sample 2, enabling pair generation for valid CID relations.

**Why Easy:** Single prompt text change; no code or tool modifications. The distinction between modifiers and disease names is straightforward for the LLM.

---

### Suggestion 3: Strengthen Negation Guard in PGM Post-Processor

**Target Agent:** `relation_result_to_id_pair` (v0003)

**What to Change:** Add "reduce the risk of", "reduces the risk of", "prevent", "prevents", "protection against", "protective effect" to the `negation_phrases` list.

**Change Details:**
- In the `negation_phrases` list, add: `'reduce the risk of'`, `'reduces the risk of'`, `'prevent'`, `'prevents'`, `'protection against'`, `'protective effect'`.

**Expected Impact:** Catches the "Aspirin may reduce the risk of heart disease" case at the PGM level, overriding the LLM's `$` verdict. This is a low-cost safety net.

**Why Easy:** Simple list addition in existing PGM code; no prompt changes, no new logic. The distance-based proximity check (50 chars) already handles context matching.