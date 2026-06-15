## 1) Metrics

**Overall Metrics (Micro)**

| Metric | Value |
|--------|-------|
| Precision | 0.5000 |
| Recall | 1.0000 |
| F1 | 0.6667 |
| TP | 2 |
| FP | 2 |
| FN | 0 |

**Overall Metrics (Macro)**

| Metric | Value |
|--------|-------|
| Precision | 0.5000 |
| Recall | 1.0000 |
| F1 | 0.6667 |

**F1 Distribution**

| Stat | Value |
|------|-------|
| Mean | 0.6667 |
| Std | 0.0000 |
| Min | 0.6667 |
| Max | 0.6667 |

**Per-Sample Metrics**

| Sample ID | TP | FP | FN | Precision | Recall | F1 |
|-----------|----|----|----|-----------|--------|----|
| 1 | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 |
| 2 | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 |

**Agent Version Mapping (Effective)**

| Agent ID | Version Used |
|----------|-------------|
| ontology_hypernym_filter | current |
| cid_pair_generate | current |
| relation_verify_llm | v0008 |
| relation_result_to_id_pair | v0003 |

## 2) FN and FP Analysis

**False Positives (2 total, 1 per sample)**

Both samples produce identical false positive relations: `D015738 | D014456` (Famotidine → ulcers). The text for both samples is irrelevant to Famotidine or ulcers:

- Sample 1 text: *"Aspirin may reduce the risk of heart disease."*
- Sample 2 text: *"Metformin is commonly used to treat type 2 diabetes."*

**Root Cause Analysis:**

The entity list for both samples contains Famotidine (D015738), delirium (D003693), and ulcers (D014456) as gold entities, despite the text having no mention of these concepts. The pipeline processes all gold entities regardless of text relevance.

The `relation_verify_llm` agent (v0008) receives the pair (Famotidine, ulcers) with the irrelevant text and returns `$` (positive). The `relation_result_to_id_pair` PGM then applies its negation/associative guards, but none trigger because the text contains no negation phrases, causal verbs, or associative phrases near the terms (the terms don't even appear in the text). The guards rely on proximity-based matching (within 50/100/15 characters), which fails when terms are absent from the text entirely.

**False Negatives:** 0 total.

## 3) Agent Modification Suggestions

### Suggestion 1: Add text-relevance guard in `relation_result_to_id_pair`

- **Target Agent:** `relation_result_to_id_pair` (v0003)
- **What to change:** Add a pre-check in the PGM process: before any other logic, verify that both `head` and `tail` surface forms appear in the `text` (case-insensitive). If either is absent, output empty list immediately.
- **Expected impact:** Eliminates both FPs (2 total) by rejecting pairs where the entities are not mentioned in the text. Precision improves from 0.5 to 1.0. Recall remains unchanged (no FNs).
- **Why easy:** Single PGM code change (add 3-4 lines at the top of the process). No prompt changes, no new tools, no external dependencies. Uses only existing state fields (`text`, `head`, `tail`).

### Suggestion 2: Strengthen `relation_verify_llm` prompt to reject text-irrelevant pairs

- **Target Agent:** `relation_verify_llm` (v0008)
- **What to change:** Add a new Assumption rule: "1.6 if {head} or {tail} does not appear in the provided text, answer '~'."
- **Expected impact:** Prevents the LLM from returning `$` for pairs where entities are absent from the text, catching the FP cases at the verification stage.
- **Why easy:** Single prompt template edit (add one line to the Assumptions section). No code changes, no new tools. Complements Suggestion 1 as a defense-in-depth measure.