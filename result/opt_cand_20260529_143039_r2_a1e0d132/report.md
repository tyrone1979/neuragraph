## 1) Metrics

**Overall Metrics (20 samples)**

| Metric | Value |
|---|---|
| Samples | 20 |
| Precision (macro avg) | 0.57 |
| Recall (macro avg) | 0.69 |
| F1 (macro avg) | 0.60 |
| Total TP | 38 |
| Total FP | 14 |
| Total FN | 32 |

**Per-Sample Metrics (selected)**

| Sample | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| 1 | 0.00 | 0.00 | 0.00 | 0 | 0 | 1 |
| 2 | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| 3 | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| 4 | 0.50 | 1.00 | 0.67 | 2 | 2 | 0 |
| 5 | 0.50 | 1.00 | 0.67 | 1 | 1 | 0 |
| 6 | 0.40 | 1.00 | 0.57 | 2 | 3 | 0 |
| 7 | 0.75 | 0.75 | 0.75 | 3 | 1 | 1 |
| 8 | 0.33 | 1.00 | 0.50 | 2 | 4 | 0 |
| 9 | 1.00 | 1.00 | 1.00 | 8 | 0 | 0 |
| 10 | 0.00 | 0.00 | 0.00 | 0 | 0 | 7 |
| 11 | 0.50 | 1.00 | 0.67 | 1 | 1 | 0 |
| 12 | 0.67 | 0.50 | 0.57 | 2 | 1 | 2 |
| 13 | 1.00 | 1.00 | 1.00 | 4 | 0 | 0 |
| 14 | 0.75 | 1.00 | 0.86 | 3 | 1 | 0 |
| 15 | 0.00 | 0.00 | 0.00 | 0 | 0 | 1 |
| 16 | 0.67 | 1.00 | 0.80 | 2 | 1 | 0 |
| 17 | 0.00 | 0.00 | 0.00 | 0 | 0 | 9 |
| 18 | 1.00 | 0.10 | 0.18 | 1 | 0 | 9 |
| 19 | 1.00 | 0.50 | 0.67 | 2 | 0 | 2 |
| 20 | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |

**Agent Version Mapping**

| graph_id | agent_id | version_used |
|---|---|---|
| wf_cid_re_llm_linear | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear | cid_pair_generate | current |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

**False Negatives (FN = 32 total)**

- **Sample 10 (7 FN):** The LLM returned `~` for `caffeine → hypertensive` and `phenylpropanolamine → Cerebral hemorrhage`. The text explicitly states "PPA/caffeine can lead to cerebral hemorrhage in previously hypertensive animals" — clear causal language. The LLM prompt's inclusion of "associated with" and "risk factor for" as causal indicators may cause confusion, but here the LLM incorrectly classified a direct causal statement as non-causal. The `relation_result_to_id_pair` PGM then correctly suppressed output because `result` was `~`.

- **Sample 17 (9 FN):** The LLM returned `~` for `dexamethasone → neuropathy`. The text states "The most frequent adverse events were ... neuropathy" in the context of a bortezomib/dexamethasone/cyclophosphamide regimen. The LLM likely classified this as a co-occurrence rather than causation. The text does not explicitly state "dexamethasone causes neuropathy" but lists it as an adverse event of the combination regimen — a borderline case where the LLM's strict interpretation missed a valid causal relation.

- **Sample 18 (9 FN):** The LLM returned `~` for `amlodipine → edema`, `amlodipine → cough`, etc. The text is a tolerability study of telmisartan+amlodipine vs amlodipine alone, listing adverse events. The LLM likely classified these as co-occurrences rather than causal side effects. The text lists "treatment-emergent adverse events" which are standardly considered drug-induced, but the LLM prompt does not explicitly instruct to treat adverse event listings as causal.

- **Sample 1 (1 FN):** The LLM returned `$` for `propofol → retrograde amnesia`, but the PGM's associative guard overrode it. The text discusses "amnesia during procedural sedation with propofol" — a clear causal relation. The PGM guard matched "associated with" near the terms and suppressed the output.

- **Sample 15 (1 FN):** The LLM returned `$` for `timolol → bradycardia`, but the PGM's negation guard overrode it. The text states "Both timolol solution and timolol gellan reduced the mean 24-hour heart rate" — a causal effect. The PGM guard likely matched "reduced" as a negation-like phrase, incorrectly suppressing the output.

**False Positives (FP = 14 total)**

- **Sample 4 (2 FP):** `flavonoids → haemopericardium` and `flavonoids → gastrointestinal haemorrhage` were predicted. The text discusses flavonoids as a *proposed mechanism* ("may increase the potency of warfarin") but does not state flavonoids directly cause these conditions. The LLM accepted "may" as causal language, and the PGM guard's associative phrase check (matching "may") did not override because the distance threshold was not met.

- **Sample 6 (3 FP):** `vancomycin → Acute renal failure`, `vancomycin → Fanconi syndrome`, `vancomycin → nephrotoxicity` were predicted. The text states "Vancomycin nephrotoxicity is infrequent" and "Renal failure developed after a prolonged course of vancomycin" — these are valid causal relations. However, the gold standard may not include these, making them FPs. The LLM correctly identified causation; the issue is likely in the gold relation set.

- **Sample 8 (4 FP):** `furosemide → Tetany`, `furosemide → rhabdomyolysis`, `furosemide → hypomagnesemia`, `furosemide → muscle weakness` were predicted. The text states "Diuretics may induce hypokalemia, hypocalcemia and hypomagnesemia" and "Tetany and rhabdomyolysis due to surreptitious furosemide" — clear causal language. The LLM correctly identified these, but the gold standard may not include all these relations.

- **Sample 14 (1 FP):** `zidovudine → megaloblastosis` with `tail_id: "-1"`. The entity `megaloblastosis` has ID `-1` (unknown/placeholder). The PGM should have filtered this out but did not, producing a relation with an invalid ID.

## 3) Agent Modification Suggestions

### Suggestion 1: Update `relation_verify_llm` prompt to treat adverse event listings as causal

- **Target agent:** `relation_verify_llm`
- **What to change:** Prompt template (human message)
- **Change:** Add explicit instruction: "If the article lists a condition as an adverse event, side effect, or treatment-emergent adverse event of a drug, treat this as causal evidence and answer '$'."
- **Expected impact:** Reduce FNs in samples 17, 18, and similar cases where adverse events are listed but not explicitly stated as "caused by". Estimated 15-20 FN reduction.
- **Why easy:** Single prompt tweak, no code changes, no new tools.

### Suggestion 2: Relax the associative guard in `relation_result_to_id_pair` PGM

- **Target agent:** `relation_result_to_id_pair`
- **What to change:** Process code — remove or significantly relax the associative guard block (lines checking `associative_phrases` within 30 chars)
- **Change:** Delete the entire associative guard section (lines 20-38 in the process). Keep only the negation guard.
- **Expected impact:** Reduce FPs caused by over-suppression of valid causal relations (e.g., sample 1). The LLM already handles associative language correctly in most cases; the PGM guard is redundant and overly aggressive.
- **Why easy:** Simple code deletion in existing PGM, no new logic.

### Suggestion 3: Add entity ID validation in `relation_result_to_id_pair` PGM

- **Target agent:** `relation_result_to_id_pair`
- **What to change:** Process code — add a guard before output
- **Change:** Add check: `if not hid or not tid or hid == '-1' or tid == '-1': __result__ = []`
- **Expected impact:** Eliminate FPs with invalid entity IDs (e.g., sample 14's `megaloblastosis` with ID `-1`). Prevents garbage relations from entering output.
- **Why easy:** Single line addition in existing PGM, no new dependencies.

### Suggestion 4: Update `relation_verify_llm` prompt to clarify "associated with" handling

- **Target agent:** `relation_verify_llm`
- **What to change:** Prompt template (human message)
- **Change:** Move "associated with" from the causal list to the non-causal list. Replace with: "Answer '$' only if the article explicitly states or clearly implies that {head} causes, induces, or results in {tail} using strong causal language (e.g., 'caused by', 'induced by', 'resulted in', 'leads to', 'due to', 'side effect of', 'adverse effect of'). Answer '~' for weak associations, correlations, co-occurrences, or when the text uses 'associated with', 'linked to', 'correlated with', 'risk factor for', 'may cause', 'can lead to'."
- **Expected impact:** Reduce FPs where weak associative language is treated as causal (e.g., sample 4's "may increase the potency"). The LLM currently treats "associated with" as causal, leading to over-prediction.
- **Why easy:** Prompt tweak only, no code changes.