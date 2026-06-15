## 1) Metrics

**Experiment Overview**
- **Experiment ID:** 2266c1ae-1f9b-4c73-8a3a-e9e8481f4a0c
- **Graph:** sg_cid_re_verify (CID RE verify pair)
- **Dataset:** regression_2_gold_test.csv (2 samples)
- **Report Mode:** table (sample_count ≤ 20)

**Agent Version Mapping**

| Agent ID | Version Used |
|---|---|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |

**Per-Sample Results**

| Sample ID | Text | Head | Tail | LLM Result | Relations Output | Expected (Gold) |
|---|---|---|---|---|---|---|
| 1 | Aspirin may reduce the risk of heart disease. | Aspirin (D001241) | heart disease (D006331) | $ | [] | FN (should be CID) |
| 2 | Metformin is commonly used to treat type 2 diabetes. | Aspirin (D001241) | heart disease (D006331) | $ | [D001241 \| D006331] | FP (head/tail mismatch) |

**Error Summary**
- **False Negatives (FN):** 1 (Sample 1)
- **False Positives (FP):** 1 (Sample 2)
- **Total Errors:** 2 out of 2 samples

## 2) FN and FP Analysis

**False Negative Analysis (Sample 1)**
- **Text:** "Aspirin may reduce the risk of heart disease."
- **LLM Output:** `$` (correctly identified causation)
- **PGM Output:** `[]` (empty - relation suppressed)
- **Cause:** The `relation_result_to_id_pair` PGM (v0003) applied its negation/associative guard. The phrase "reduce the risk of" triggered the associative guard logic. The text contains "risk of" within 15 characters of "heart disease" (tail), causing `override = True` and suppressing the valid relation. This is a false suppression: "reduce the risk of" is a protective/causal relationship (head reduces risk of tail), not an associative non-causal statement.

**False Positive Analysis (Sample 2)**
- **Text:** "Metformin is commonly used to treat type 2 diabetes."
- **LLM Output:** `$` (incorrectly identified causation)
- **PGM Output:** `[D001241 | D006331]` (Aspirin→heart disease)
- **Cause:** The LLM prompt received `head = "Aspirin"` and `tail = "heart disease"`, but the text is about Metformin and type 2 diabetes. The LLM incorrectly output `$` despite the text having no mention of Aspirin or heart disease. The PGM then passed this through without any guard against head/tail mismatch with the text content. The root cause is the LLM failing to verify that the head and tail entities actually appear in the text with the claimed relationship.

## 3) Agent Modification Suggestions

### Suggestion 1: Fix FN - Update PGM associative guard for protective relationships
- **Target Agent:** `relation_result_to_id_pair` (v0003)
- **What to Change:** In the PGM process, add a check before the associative guard: if the text contains phrases indicating protective/reducing effect (e.g., "reduce risk", "decrease risk", "lower risk", "prevent") near both head and tail, skip the associative override.
- **Expected Impact:** Sample 1 would correctly output `[D001241 | D006331]` instead of `[]`. This directly fixes the FN.
- **Why Easy:** Single PGM code change. Add a `protective_phrases` list and check proximity similar to existing `causal_patterns` logic. No new dependencies.

### Suggestion 2: Fix FP - Add head/tail presence verification in PGM
- **Target Agent:** `relation_result_to_id_pair` (v0003)
- **What to Change:** Before outputting the relation, add a guard that checks if both `head` and `tail` strings appear in the `text` (case-insensitive). If either is absent, output `[]`.
- **Expected Impact:** Sample 2 would output `[]` because "Aspirin" and "heart disease" do not appear in the text about Metformin. This directly fixes the FP.
- **Why Easy:** Single PGM code change. Simple string containment check using existing `text_lower`, `head_lower`, `tail_lower` variables. No new dependencies.

### Suggestion 3: Improve LLM prompt to verify entity presence
- **Target Agent:** `relation_verify_llm` (v0010)
- **What to Change:** Add a new Assumption rule: "1.6 if {head} or {tail} does not appear in the provided text, answer '~' immediately."
- **Expected Impact:** The LLM would output `~` for Sample 2, preventing the FP at the source. This also catches similar mismatches in other samples.
- **Why Easy:** Single prompt template change. No code changes needed. The LLM already has Assumption rules that trigger immediate `~` output.