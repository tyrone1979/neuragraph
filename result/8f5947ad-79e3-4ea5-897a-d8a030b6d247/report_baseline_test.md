## 1) Metrics

| Metric | Value |
|--------|-------|
| Sample Count | 2 |
| Report Mode | table |

**Agent Version Mapping (authoritative)**

| Agent ID | Version Used |
|----------|-------------|
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
|-----------|------|----------------|--------|-------|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin → heart disease) | $ (positive) | False positive: Aspirin reduces risk, does not induce |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | N/A | No disease entity extracted; no pairs generated |

**Error Summary**
- **False Positives**: 1 (sample 1: Aspirin → heart disease)
- **False Negatives**: 1 (sample 2: missing "type 2 diabetes" as Disease entity)

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**
- **Text**: "Aspirin may reduce the risk of heart disease."
- **Entities extracted**: Aspirin (Chemical, id=1), heart disease (Disease, id=1)
- **Pair generated**: Aspirin → heart disease
- **LLM verdict**: `$` (induces)
- **Root cause**: The `relation_verify_llm` prompt (v0010) does not have a condition to detect protective/reductive relationships. The text states Aspirin *reduces* risk, which is the opposite of causation. The prompt's Condition 1 checks for "caused or induced" patterns, Condition 4 checks for "because of", but there is no rule to handle "reduces risk of", "prevents", or "protects against". The `relation_result_to_id_pair` PGM's negation guard only checks for explicit negation phrases like "did not cause" — "reduces the risk of" is not in the negation list. The associative guard checks for "associated with" etc. but "reduces the risk of" is not matched.

**False Negative Analysis (Sample 2)**
- **Text**: "Metformin is commonly used to treat type 2 diabetes."
- **Entities extracted**: Metformin (Chemical, id=1) — only one entity
- **Missing entity**: "type 2 diabetes" (Disease) was not extracted by upstream NER
- **Root cause**: The upstream NER pipeline (not shown in this package) failed to extract "type 2 diabetes" as a Disease entity. Since `e2e_entities_passthrough` only receives entities from the NER output, the disease is missing. The `cid_pair_generate` PGM requires at least one Chemical and one Disease to form pairs; with only a Chemical, zero pairs are generated. This is an upstream NER recall issue, not a relation verification issue.

## 3) Agent Modification Suggestions

### Suggestion 1: Add protective/reductive relationship detection to `relation_verify_llm` prompt

- **Target agent**: `relation_verify_llm` (v0010)
- **What to change**: Add a new Condition to the prompt template (human section) that handles protective/reductive/preventive relationships
- **Proposed addition** (insert after existing Condition 6):
  ```
  7. if the article states that {head} reduces, prevents, protects against, lowers the risk of, or is used to treat {tail} (e.g., '{head} reduces risk of {tail}', '{head} prevents {tail}', '{head} is used to treat {tail}'), answer '~'
  ```
- **Expected impact**: Eliminates the false positive in sample 1 and similar cases where a drug is described as protective rather than causative
- **Why easy**: Single prompt template edit; no code changes, no new tools, no external dependencies

### Suggestion 2: Add "reduces risk of" to negation guard in `relation_result_to_id_pair`

- **Target agent**: `relation_result_to_id_pair` (v0003)
- **What to change**: Add protective/reductive phrases to the `negation_phrases` list in the PGM process
- **Proposed change**: Append to `negation_phrases`:
  ```python
  'reduces risk of', 'reduces the risk of', 'protects against', 'prevents',
  'decreases risk of', 'lowers risk of', 'used to treat', 'used for treatment of'
  ```
- **Expected impact**: Provides a second layer of defense against false positives where the LLM misses protective relationships
- **Why easy**: Single list addition in existing PGM code; no structural changes

### Suggestion 3: Add "treatment" and "therapeutic" context detection to `relation_verify_llm` prompt

- **Target agent**: `relation_verify_llm` (v0010)
- **What to change**: Add a new Assumption (before existing Assumption 1.1) that handles therapeutic/treatment contexts
- **Proposed addition** (insert as new Assumption 1.1, renumber existing):
  ```
  1.1 if the article states that {head} is used to treat, manage, prevent, or reduce risk of {tail} (e.g., '{head} is used to treat {tail}', '{head} reduces risk of {tail}', '{head} prevents {tail}'), answer '~'
  ```
- **Expected impact**: Catches both sample 1 (reduces risk) and sample 2 (used to treat) patterns at the assumption level, which takes priority over conditions
- **Why easy**: Single prompt template edit; leverages existing assumption mechanism