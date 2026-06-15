## 1) Metrics

**Experiment Overview**
- **Experiment ID:** 71436c42-6786-40eb-a2c6-24b46eab96ca
- **Runner:** sg_e2e_cid_re (regression gold_test_only)
- **Dataset:** regression_2_gold_test.csv (2 samples)
- **Status:** completed
- **Report Mode:** table (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| e2e_entities_passthrough | current |
| e2e_synonym_filter | current |
| e2e_entities_assign_group_ids | current |
| e2e_entity_aliases_snapshot | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |
| cid_pair_generate | current |

**Per-Sample Results**

| Sample ID | Text | Pairs Generated | Result | Notes |
|---|---|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin → heart disease) | $ (induces) | False Positive: Aspirin reduces risk, does not induce heart disease |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | N/A | No Disease entity extracted; only Chemical (Metformin) present |

**Overall Metrics**
- Total samples: 2
- Samples with pairs: 1
- Correct predictions: 0
- False positives: 1 (sample 1)
- False negatives: 0 (no gold relations missed; sample 2 had no pairs generated due to missing Disease entity)

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**

- **Text:** "Aspirin may reduce the risk of heart disease."
- **Predicted Relation:** Aspirin (head_id: 1) induces heart disease (tail_id: 1)
- **Gold:** No relation (Aspirin reduces risk, not induces)
- **Cause:** The `relation_verify_llm` agent (v0010) incorrectly classified this as `$` (induces). The prompt's Condition 4 ("if the article mentions {tail} was reported in the percentage of patients because of {head}") does not apply here. The text uses "may reduce the risk of" which is a protective/negative association. The LLM failed to recognize that "reduces the risk of" is the opposite of causation. The `relation_result_to_id_pair` PGM's negation guard did not catch this because "reduce the risk of" is not in the negation_phrases list (which focuses on explicit negation like "did not cause").

**False Negative Analysis (Sample 2)**

- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **Predicted Pairs:** 0
- **Gold:** Potentially a Chemical-Disease pair (Metformin → type 2 diabetes) but as treatment, not causation
- **Cause:** The `e2e_hypernym_filter` or upstream entity extraction failed to produce a Disease entity. Only "Metformin" (Chemical) was present in `filtered_entities`. The text mentions "type 2 diabetes" but it was either not extracted by the NER or was filtered out. Since `cid_pair_generate` requires at least one Chemical and one Disease entity, no pairs were generated.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix FP on "reduces the risk of" patterns

**Target Agent:** `relation_result_to_id_pair` (PGM, v0003)

**What to Change:** Add "reduces the risk of" and "decreases the risk of" to the `negation_phrases` list in the PGM process.

**Expected Impact:** Prevents false positives where the text describes a protective/reducing effect rather than causation. This would have caught the FP in sample 1.

**Why Easy:** This is a simple string addition to an existing list in a PGM agent. No LLM changes, no new tools, no external dependencies. The PGM already has a negation guard mechanism; this extends its coverage to a common biomedical pattern.

---

### Suggestion 2: Improve Disease entity extraction for treatment contexts

**Target Agent:** `e2e_hypernym_filter` (LLM, current)

**What to Change:** Add a step in the prompt to explicitly preserve Disease entities that appear in treatment contexts (e.g., "used to treat {Disease}", "therapy for {Disease}", "treatment of {Disease}").

**Expected Impact:** Reduces false negatives where Disease entities are dropped because they appear in a treatment context rather than a causation context. Would have preserved "type 2 diabetes" in sample 2.

**Why Easy:** This is a prompt tweak only. The LLM already receives the full text and entity list. Adding a preservation rule for treatment-context diseases is a low-complexity change that does not require new tools or external data.

---

### Suggestion 3: Strengthen LLM reasoning for protective/negative associations

**Target Agent:** `relation_verify_llm` (LLM, v0010)

**What to Change:** Add a new Assumption or Condition to the prompt that explicitly handles protective/reducing effects. For example: "If the article states that {head} reduces, decreases, prevents, or protects against {tail}, answer '~'."

**Expected Impact:** Prevents the LLM from classifying protective associations as causal. This directly addresses the FP in sample 1.

**Why Easy:** This is a prompt addition only. The existing prompt already has numbered Assumptions and Conditions. Adding one more Assumption for protective effects is straightforward and does not require any code changes or external dependencies.