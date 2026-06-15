## 1) Metrics

**Experiment Overview**
- **Experiment ID:** 35bae8bd-a164-4b32-bd66-35a709b4259c
- **Graph:** wf_e2e_flair_opt_re
- **Dataset:** regression_2_no_gold_test.csv (2 samples)
- **Status:** completed
- **Report Mode:** table (sample_count ≤ 20)

**Overall Metrics (Macro)**

| Metric | Value |
|--------|-------|
| Precision | 0.0 |
| Recall | 0.0 |
| F1 | 0.0 |
| F1 Mean | 0.0 |
| F1 Std | 0.0 |
| F1 Min | 0.0 |
| F1 Max | 0.0 |

**Per-Sample Metrics**

| Sample ID | Text | Predicted Pairs | Gold Pairs | Precision | Recall | F1 |
|-----------|------|----------------|------------|-----------|--------|-----|
| 1 | Aspirin may reduce the risk of heart disease. | 0 | 0 | N/A | N/A | N/A |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 1 (CHEBI:6801 \| MESH:D003924) | 0 | 0.0 | 0.0 | 0.0 |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_assign_group_ids | current |
| e2e_entities_dedup_by_id | current |
| e2e_entities_passthrough | current |
| e2e_entity_aliases_snapshot | current |
| e2e_hypernym_filter | current |
| e2e_synonym_filter | current |
| eval_metrics_relation | current |
| ner_entities_to_re_format | current |
| text_sentence_split | current |
| ner_flair_sent | current |

**Error Summary**
- **False Positives:** 1 (Sample 2: predicted Metformin induces type 2 diabetes, but ground truth has no relation)
- **False Negatives:** 0 (no gold relations missed)

## 2) FN and FP Analysis

**False Positive Analysis (Sample 2)**

**Text:** "Metformin is commonly used to treat type 2 diabetes."

**Predicted Relation:** CHEBI:6801 (Metformin) | MESH:D003924 (type 2 diabetes) — verdict: `$` (induces)

**Ground Truth:** No relation (empty gold_relations)

**Root Cause Analysis:**

The pipeline correctly identifies entities (Metformin as Chemical, type 2 diabetes as Disease) and generates a pair. The `relation_verify_llm` (v0010) incorrectly outputs `$` for this pair. The text explicitly states Metformin is used to *treat* type 2 diabetes — the opposite of causation. The LLM prompt's Condition 1.5 should catch this ("if {head} is used as... treatment for {tail}... answer '~'"), but it failed to apply.

The `relation_result_to_id_pair` PGM then processes the `$` result. Its negation guard checks for phrases like "did not cause" but does not check for treatment/rescue patterns. The causal override finds no explicit causal language. The associative guard checks for "associated with" etc. but the text has no such phrase near the terms. So the pair passes through as a positive relation.

**False Negative Analysis:** None — no gold relations were missed.

## 3) Agent Modification Suggestions

### Suggestion 1: Strengthen treatment/rescue detection in `relation_verify_llm` prompt

**Target Agent:** `relation_verify_llm` (v0010)

**What to Change:** Add a new Assumption (1.6) to the prompt template's `human` field, placed before Conditions.

**Proposed Addition (after Assumption 1.5):**
```
1.6 if the article states that {head} is used to treat, manage, prevent, or ameliorate {tail} (e.g., '{head} is used to treat {tail}', '{head} for {tail}', '{head} treats {tail}', '{head} is a treatment for {tail}', '{head} reduces {tail} risk'), answer '~'.
```

**Expected Impact:** Eliminates the observed FP (Sample 2) and similar FPs where a drug is described as a treatment for a disease. This is the most common cause of false positives in CID extraction from treatment-oriented sentences.

**Why Easy:** Single prompt addition — no code changes, no new tools, no external dependencies. The pattern is already partially covered by Assumption 1.5 (resuscitation/rescue), but needs generalization to all treatment contexts.

### Suggestion 2: Add treatment negation guard in `relation_result_to_id_pair` PGM

**Target Agent:** `relation_result_to_id_pair` (v0003)

**What to Change:** Add treatment-related phrases to the `negation_phrases` list in the PGM process code.

**Proposed Change:** Append to `negation_phrases`:
```python
'treat', 'treatment', 'used to treat', 'therapy for', 'therapeutic',
'prevent', 'prevention', 'manage', 'management', 'ameliorate',
'reduce risk', 'protective'
```

**Expected Impact:** Provides a second line of defense when the LLM misses a treatment context. The guard checks if any treatment phrase appears within 50 characters of head or tail terms, overriding a `$` verdict.

**Why Easy:** Simple list extension in existing PGM code. No new logic or external dependencies. Complements the prompt fix with a deterministic fallback.

### Suggestion 3: Add "treatment" to causal override patterns in `relation_result_to_id_pair`

**Target Agent:** `relation_result_to_id_pair` (v0003)

**What to Change:** In the causal override section, add a check that if treatment language is found near head/tail, skip the associative guard override (i.e., treat it as non-causal).

**Proposed Change:** After the `has_causal` check, add:
```python
# Treatment override: if treatment language near terms, do not output relation
treatment_phrases = ['used to treat', 'treatment of', 'therapy for', 'treats']
for phrase in treatment_phrases:
    pidx = text_lower.find(phrase)
    if pidx == -1:
        continue
    for term in [head_lower, tail_lower]:
        if not term:
            continue
        tidx = text_lower.find(term)
        if tidx == -1:
            continue
        if abs(pidx - tidx) <= 50:
            override = True
            break
    if override:
        break
```

**Expected Impact:** Catches cases where the LLM outputs `$` but the text clearly indicates treatment. This is a more targeted fix than the negation guard (which uses generic negation phrases) and directly addresses the observed FP pattern.

**Why Easy:** Follows existing code pattern (negation guard, causal override, associative guard). No new imports or external dependencies.