## 1) Metrics

**Experiment Overview**
| Metric | Value |
|--------|-------|
| Experiment ID | c2a2b5ad-c532-4aaa-82ac-d773f67abb5c |
| Graph | sg_e2e_cid_re |
| Dataset | regression_2_gold_test.csv |
| Samples | 2 |
| Report Mode | table |

**Agent Version Mapping**
| Agent ID | Version Used |
|----------|-------------|
| e2e_entities_passthrough | current |
| e2e_synonym_filter | current |
| e2e_entities_assign_group_ids | current |
| e2e_entity_aliases_snapshot | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |
| cid_pair_generate | current |
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |

**Per-Sample Metrics**
| Sample ID | Text | Pairs Generated | Result | Notes |
|-----------|------|----------------|--------|-------|
| 1 | Aspirin may reduce the risk of heart disease. | 1 (Aspirin→heart disease) | $ | False positive: Aspirin reduces risk, does not induce |
| 2 | Metformin is commonly used to treat type 2 diabetes. | 0 | N/A | No Disease entity extracted; no pairs generated |

**Error Summary**
- **False Positives**: 1 (Sample 1: Aspirin→heart disease)
- **False Negatives**: 1 (Sample 2: Metformin→type 2 diabetes relation missed)
- **Total Errors**: 2

## 2) FN and FP Analysis

**False Positive Analysis (Sample 1)**
- **Text**: "Aspirin may reduce the risk of heart disease."
- **Predicted Relation**: Aspirin induces heart disease ($)
- **Root Cause**: The `relation_verify_llm` agent (v0010) incorrectly applied Condition 3 (combination/co-treatment regimen) or Condition 4 (percentage-based causation) despite the text clearly stating a protective/reducing effect. The PGM guard in `relation_result_to_id_pair` (v0003) failed to override because:
  - The negation guard checks for phrases like "did not cause" but not for protective/reducing language ("reduce the risk of")
  - The associative guard checks for "associated with" within 15 chars, but "reduce the risk of" is not in the associative phrases list
  - The causal override correctly found no causal language, but the associative guard did not catch "reduce the risk of" as an associative/non-causal phrase

**False Negative Analysis (Sample 2)**
- **Text**: "Metformin is commonly used to treat type 2 diabetes."
- **Missing Relation**: Metformin→type 2 diabetes (treatment relation, not causation)
- **Root Cause**: The `e2e_entities_passthrough` agent filtered out "type 2 diabetes" because it has no `label` or `type` field in the input entities. The input entities only contain `[{"text": "Metformin", "id": "1", "label": "Chemical"}]` — the Disease entity was never provided to the pipeline. This is a data/input issue: the gold test dataset did not include the Disease entity for this sample.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix FP on protective/reducing language
- **Target Agent**: `relation_result_to_id_pair` (v0003)
- **What to Change**: Add protective/reducing phrases to the associative guard list in the PGM process
- **Change Details**: Add to the `associative_phrases` list: `'reduce the risk of'`, `'reduces the risk of'`, `'reduced risk of'`, `'protective effect'`, `'prevent'`, `'prevents'`, `'prevented'`, `'decrease the risk'`, `'decreases the risk'`, `'lower the risk'`, `'lowers the risk'`
- **Expected Impact**: Eliminates the FP on Sample 1 and similar protective/reducing language patterns
- **Why Easy**: Single-line addition to an existing list in a PGM agent; no prompt changes, no new tools, no external dependencies

### Suggestion 2: Improve LLM prompt to handle protective/reducing language
- **Target Agent**: `relation_verify_llm` (v0010)
- **What to Change**: Add a new Assumption to the prompt template
- **Change Details**: Add Assumption 1.6: "if the article states that {head} reduces, prevents, protects against, or lowers the risk of {tail}, answer '~'"
- **Expected Impact**: Prevents the LLM from outputting '$' for protective/reducing relationships, reducing FP rate
- **Why Easy**: Single assumption added to existing prompt template; no code changes, no new tools

### Suggestion 3: Improve Disease entity extraction for FN cases
- **Target Agent**: `e2e_entities_passthrough`
- **What to Change**: Add a fallback NER step when input entities are missing Disease labels
- **Change Details**: After the current dedup logic, if no Disease entities exist in the output, attempt to extract Disease entities from the text using a simple pattern-based approach (e.g., look for common disease suffixes like "-itis", "-osis", "-emia", "-pathy", or known disease terms like "diabetes", "cancer", "hypertension")
- **Expected Impact**: Recovers the FN on Sample 2 by generating the missing Disease entity
- **Why Easy**: PGM agent modification; no new LLM calls, no external APIs; uses simple string matching on the text