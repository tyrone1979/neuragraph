## 1) Metrics

**Experiment Overview**
- **Experiment ID:** `3a0c892f-46f5-49c8-82dc-f958a95a6bcf`
- **Graph:** `sg_re_tree` (Tree-based RE)
- **Dataset:** `regression_2_gold_test.csv` (2 samples)
- **Report Mode:** `table` (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| `syntax_dep_parse` | current |
| `relation_from_tree_llm` | current |

**Per-Sample Results**

| Sample ID | Sentence | Extracted Triples |
|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | Aspirin \| reduce \| risk of heart disease |
| 2 | Metformin is commonly used to treat type 2 diabetes. | Metformin \| used \| type 2 diabetes |

**Metrics Summary:** No aggregate metrics available (`metrics_summary.sample_count = 0`). No gold standard comparison was performed.

---

## 2) FN and FP Analysis

**False Negatives (FN) Analysis**

- **Sample 1:** The extracted triple `Aspirin | reduce | risk of heart disease` captures the general relationship but misses the specific causal link between Aspirin and heart disease. The dependency tree correctly identifies `Aspirin` as `nsubj` of `reduce` and `risk of heart disease` as `obj`, but the LLM fails to extract the more specific relation `Aspirin | reduce | heart disease` (the actual disease entity).
- **Sample 2:** The extracted triple `Metformin | used | type 2 diabetes` captures the treatment relationship but uses the passive verb `used` instead of the active verb `treat`. The dependency tree shows `treat` as the main verb with `type 2 diabetes` as its `obj`, but the LLM extracted the auxiliary verb `used` as the relation verb.

**False Positives (FP) Analysis**

- No false positives detected in the extracted triples. Both triples are semantically valid given the input sentences.

**Root Cause Analysis**

1. **Verb selection issue (Sample 2):** The `relation_from_tree_llm` agent selects the passive auxiliary verb `used` instead of the active infinitive verb `treat`. The prompt instructs extraction of "main verb (lemma or surface)" but does not specify how to handle auxiliary verbs vs. main verbs in complex verb chains (e.g., `is used to treat`).
2. **Entity granularity (Sample 1):** The LLM extracts the full noun phrase `risk of heart disease` as the tail entity rather than the core disease entity `heart disease`. The prompt does not specify how to handle prepositional modifiers within noun phrases.

---

## 3) Agent Modification Suggestions

### Suggestion 1: Improve verb selection in `relation_from_tree_llm`

- **Target Agent:** `relation_from_tree_llm`
- **What to Change:** Prompt template (human section)
- **Change:** Add explicit instruction to prefer the main lexical verb (infinitive or finite) over auxiliary/passive verbs when multiple verbs exist in a clause. Add: "When a verb chain exists (e.g., auxiliary + main verb), extract the main lexical verb (the one carrying the primary semantic meaning), not the auxiliary."
- **Expected Impact:** Fixes Sample 2 FN where `used` was extracted instead of `treat`. Reduces similar FNs across all sentences with passive or compound verb constructions.
- **Why Easy:** Single prompt modification, no code changes, no new dependencies.

### Suggestion 2: Improve entity boundary detection in `relation_from_tree_llm`

- **Target Agent:** `relation_from_tree_llm`
- **What to Change:** Prompt template (human section)
- **Change:** Add instruction to extract the core entity (head noun) when the object contains prepositional modifiers. Add: "For tail entities with prepositional modifiers (e.g., 'risk of heart disease'), extract the core entity after the preposition (e.g., 'heart disease') rather than the full phrase."
- **Expected Impact:** Fixes Sample 1 FN where `risk of heart disease` was extracted instead of `heart disease`. Improves entity granularity across all sentences with prepositional modifiers.
- **Why Easy:** Single prompt modification, no code changes, no new dependencies.