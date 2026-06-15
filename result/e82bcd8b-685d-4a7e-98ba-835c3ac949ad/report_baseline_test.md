## 1) Metrics

**Overall Metrics**

| Metric | Value |
|--------|-------|
| Sample Count | 2 |
| Report Mode | table |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| text_coreference | current |
| text_sentence_split | current |
| syntax_dep_parse | current |
| relation_from_tree_llm | current |
| kg_triple_persist | current |

**Per-Sample Metrics**

| Sample ID | Text |
|-----------|------|
| 1 | Aspirin may reduce the risk of heart disease. |
| 2 | Metformin is commonly used to treat type 2 diabetes. |

No metrics_summary or per-sample evaluation metrics were provided in the experiment package. The states contain only raw input text for 2 samples with no gold labels, predictions, or computed metrics.

## 2) FN and FP Analysis

**Analysis Limitation**: The experiment package contains no evaluation results—no gold labels, no predictions, no false negatives, no false positives, and no examples_detail. The states only include the raw input text for two samples. Without any output data or ground truth, no FN/FP analysis can be performed.

**Observations from Available Data**:
- Sample 1: "Aspirin may reduce the risk of heart disease." — This contains a potential causal relation (Aspirin → reduce → heart disease).
- Sample 2: "Metformin is commonly used to treat type 2 diabetes." — This contains a treatment relation (Metformin → treat → type 2 diabetes).

The graph flow processes these through: coreference resolution → sentence splitting → dependency parsing → relation extraction from tree → CSV persistence. No errors or outputs are recorded in the provided states.

## 3) Agent Modification Suggestions

**Suggestion 1: Improve relation extraction prompt for causal and treatment relations**

- **Target Agent**: `relation_from_tree_llm`
- **What to Change**: Modify the prompt template's human section to explicitly include causal and treatment relation patterns.
- **Current Prompt**: Extracts only `nsubj → verb → obj/iobj/obl` triples.
- **Proposed Change**: Add examples of causal verbs (e.g., "reduce", "increase", "cause", "prevent") and treatment verbs (e.g., "treat", "manage", "used for") to the prompt. Change the triple format instruction to: "head | relation_verb | tail" where relation_verb captures the semantic relation (e.g., "reduces_risk_of", "treats").
- **Expected Impact**: Better capture of biomedical relations that are not simple subject-verb-object (e.g., "Aspirin may reduce the risk of heart disease" → "Aspirin | reduces_risk_of | heart disease").
- **Why Easy**: Single prompt edit in existing agent meta; no new tools or dependencies.

**Suggestion 2: Add post-processing to normalize relation verbs**

- **Target Agent**: `kg_triple_persist`
- **What to Change**: Add a small PGM process step to normalize relation verbs to a canonical set (e.g., "treats", "causes", "prevents", "associated_with").
- **Proposed Change**: In the `process` field, add logic to map common verb phrases to canonical relations: `"used to treat" → "treats"`, `"may reduce the risk of" → "reduces_risk_of"`.
- **Expected Impact**: Consistent relation types in output CSV, enabling better downstream aggregation.
- **Why Easy**: PGM process field is already editable; no new agents or external calls needed.

**Suggestion 3: Improve dependency parsing for compound biomedical terms**

- **Target Agent**: `syntax_dep_parse`
- **What to Change**: Add instruction in the prompt to correctly identify compound nouns and multi-word biomedical terms (e.g., "type 2 diabetes", "heart disease") as single tokens using the CoNLL-U multi-word token format (ID range with .1, .2).
- **Proposed Change**: Add to the prompt: "For multi-word biomedical terms (e.g., 'type 2 diabetes', 'heart disease'), use the CoNLL-U multi-word token format (e.g., 3-4 type 2 diabetes) to keep them as single semantic units."
- **Expected Impact**: The relation extraction agent will receive cleaner dependency trees where biomedical entities are not split across multiple tokens, improving triple extraction accuracy.
- **Why Easy**: Single prompt edit in existing agent meta.