## 1) Metrics

**Overall Metrics**

| Metric | Value |
|--------|-------|
| Precision | 0.75 |
| Recall | 0.80 |
| F1 | 0.72 |
| True Positives | 6 |
| False Positives | 2 |
| False Negatives | 2 |

**Per-Sample Metrics**

| Sample ID | Precision | Recall | F1 | TP | FP | FN |
|-----------|-----------|--------|----|----|----|----|
| 1 | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| 2 | 0.67 | 1.0 | 0.8 | 2 | 1 | 0 |
| 3 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2 |
| 4 | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| 5 | 0.67 | 1.0 | 0.8 | 2 | 1 | 0 |

**Agent Version Mapping**

| Graph ID | Agent ID | Version Used |
|----------|----------|--------------|
| wf_cid_re_llm_linear | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear | cid_pair_generate | current |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

**False Negatives (Sample 3)**

Sample 3 has 2 false negatives and 0 false positives. The text describes "Hepatic adenomas and focal nodular hyperplasia of the liver in young women on oral contraceptives" and states these are "presumably associated with the use of oral contraceptives." The LLM returned `~` for the pair `oral contraceptives → focal nodular hyperplasia`. The word "presumably" triggered the associative language guard in `relation_result_to_id_pair`, which overrode the `$` result to empty. However, the text explicitly states a causal association ("presumably associated with the use of oral contraceptives"), which is a legitimate causal relation in biomedical literature. The guard is too aggressive—it treats "presumably" as a definitive override, but in this context it signals a reported causal link.

**False Positives (Samples 2 and 5)**

Sample 2 has 1 FP: `diuretic → diabetes` (D004232 | D003920). The text lists "diabetes" as a predictor variable in a study about decreased renal function, not as a condition caused by diuretic. The LLM returned `~`, but the guard did not override because no associative phrase was within 100 characters of both terms. The pair was generated because both entities appear in the filtered list, but there is no causal statement linking them.

Sample 5 has 1 FP: `Na → convulsions` (D012964 | D012640). The text mentions "Inhibition of Na(+) channels by local anesthetics may regulate desipramine-induced down-regulation of NET function." The LLM returned `$`, and the guard did not override. However, "Na" here refers to sodium ions/channels, not a chemical that causes convulsions. The entity `Na` with ID D012964 is a generic chemical entity that should not be paired with convulsions in this context.

**Root Cause Analysis**

The FP issues stem from two sources:
1. **Overly permissive pair generation**: `cid_pair_generate` creates all possible Chemical–Disease pairs from filtered entities without any semantic filtering. This generates many implausible pairs (e.g., `creatinine → heart failure`, `Na → convulsions`).
2. **Insufficient guard coverage**: The associative language guard in `relation_result_to_id_pair` only checks for specific phrases within 100 characters, missing cases where the LLM incorrectly returns `$` for non-causal pairs.

The FN issue stems from the guard being too aggressive with words like "presumably" that appear in legitimate causal statements.

## 3) Agent Modification Suggestions

### Suggestion 1: Relax associative language guard in `relation_result_to_id_pair`

- **Target agent**: `relation_result_to_id_pair`
- **What to change**: Modify the PGM process to only override `$` to empty when the associative phrase appears in a speculative context (e.g., preceded by "may be", "could be", "possible") rather than any occurrence. Change the override logic to check if the associative phrase is part of a speculative construction (e.g., "may be associated with", "could be linked to") vs. a definitive statement ("was associated with", "is associated with").
- **Expected impact**: Reduces false negatives in Sample 3 while maintaining FP protection. The word "presumably" in Sample 3 is used in a definitive statement ("presumably associated with the use of oral contraceptives"), which should not trigger override.
- **Why easy**: Single PGM code change in `relation_result_to_id_pair`. No new tools or external dependencies.

### Suggestion 2: Add semantic plausibility filter to `cid_pair_generate`

- **Target agent**: `cid_pair_generate`
- **What to change**: Add a simple PGM guard that checks if the head and tail entities co-occur within a reasonable window in the text (e.g., within 500 characters). If they don't co-occur, skip generating that pair. This can be implemented by searching for the head text and tail text in the `text` field and checking their distance.
- **Expected impact**: Reduces false positives by eliminating pairs where the chemical and disease never appear together in the text. For Sample 2, `diuretic` and `diabetes` appear in a list of predictors, not in a causal context, but they do co-occur in the text, so this would not eliminate that FP. However, it would eliminate many implausible pairs like `creatinine → heart failure` where the terms appear in different contexts.
- **Why easy**: Single PGM code change in `cid_pair_generate`. The `text` field is available in the state. No new tools or external dependencies.

### Suggestion 3: Improve `relation_verify_llm` prompt to handle generic entities

- **Target agent**: `relation_verify_llm`
- **What to change**: Add a sentence to the prompt: "If the head entity is a generic chemical (e.g., 'Na', 'sodium', 'calcium', 'potassium') that refers to an ion or element rather than a specific drug, return '~' unless the article explicitly states it caused the disease."
- **Expected impact**: Reduces false positives for generic chemical entities like `Na → convulsions` in Sample 5. The LLM currently returns `$` because "Na(+) channels" appears near "convulsions," but the text does not state that sodium causes convulsions.
- **Why easy**: Single prompt template change in `relation_verify_llm`. No new tools or external dependencies.