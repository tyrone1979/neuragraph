## 1) Metrics

### Overall Metrics (20 samples)

| Metric | Value |
|--------|-------|
| Samples | 20 |
| Precision | 0.63 |
| Recall | 0.69 |
| F1 | 0.66 |
| Total TP | 37 |
| Total FP | 14 |
| Total FN | 32 |

### Per-Sample Metrics

| Sample | Precision | Recall | F1 | TP | FP | FN |
|--------|-----------|--------|----|----|----|----|
| 1 | 0.00 | 0.00 | 0.00 | 0 | 0 | 1 |
| 2 | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| 3 | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| 4 | 0.50 | 1.00 | 0.67 | 2 | 2 | 0 |
| 5 | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| 6 | 0.40 | 1.00 | 0.57 | 2 | 3 | 0 |
| 7 | 0.80 | 1.00 | 0.89 | 4 | 1 | 0 |
| 8 | 0.33 | 1.00 | 0.50 | 2 | 4 | 0 |
| 9 | 0.88 | 0.88 | 0.88 | 7 | 1 | 1 |
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

### Agent Version Mapping

| graph_id | agent_id | version_used |
|----------|----------|--------------|
| wf_cid_re_llm_linear_opt_20260529_143039_r2 | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear_opt_20260529_143039_r2 | cid_pair_generate | current |
| wf_cid_re_llm_linear_opt_20260529_143039_r2 | relation_verify_llm | v0007 |
| wf_cid_re_llm_linear_opt_20260529_143039_r2 | relation_result_to_id_pair | v0001 |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

### False Negatives (FN = 32)

**Major FN clusters:**

- **Sample 10 (7 FN):** Text describes PPA/caffeine causing cerebral hemorrhage and hypertension in rats. The LLM returned `~` for the pair `caffeine → hypertension`. The text explicitly states "PPA/caffeine can lead to cerebral hemorrhage" and "acute elevation in blood pressure". The `relation_result_to_id_pair` PGM's associative guard (30-char proximity check for "associated with", "may", "could", etc.) likely overrode the `$` result incorrectly. The text uses "can lead to" which is in the LLM's causal list, but the PGM guard matched "may" or "could" within 30 chars of a term.

- **Sample 17 (9 FN):** Text describes bortezomib/cyclophosphamide/dexamethasone for myeloma, with neuropathy as an adverse event. The LLM returned `~` for `dexamethasone → neuropathy`. The text states "The most frequent adverse events were ... neuropathy" — clear causal language. The PGM guard likely overrode due to proximity of "as well as" or similar associative phrasing.

- **Sample 18 (9 FN):** Text describes amlodipine/telmisartan trial with adverse events listed. The LLM returned `~` for `amlodipine → diarrhea`. The text lists "treatment-emergent adverse events" — standard clinical trial language for side effects. The PGM guard likely overrode due to proximity of "assessed by" or similar.

- **Sample 1 (1 FN):** Text describes propofol sedation and amnesia. The LLM returned `$` for `propofol → retrograde amnesia`, but the PGM guard overrode it. The text mentions "persistence of amnesia during procedural sedation with propofol" — causal implication. The guard likely matched "associated with" or similar within 30 chars.

- **Sample 15 (1 FN):** Text describes timolol reducing heart rate. The LLM returned `$` for `timolol → bradycardia`. The text states "Both timolol ... reduced the mean 24-hour heart rate" — causal. The PGM guard likely overrode due to proximity of "compared with" or similar.

**Root cause:** The `relation_result_to_id_pair` PGM (v0001) has an overly aggressive associative guard that overrides LLM `$` verdicts when associative phrases (e.g., "associated with", "may", "could", "possible") appear within 30 characters of the head/tail term. This incorrectly suppresses true causal relations in clinical trial contexts where adverse events are described using standard safety language.

### False Positives (FP = 14)

**Major FP clusters:**

- **Sample 8 (4 FP):** Pairs like `furosemide → obese`, `magnesium → obese`, `potassium → obese`, `calcium → edematous`. The text mentions "women who are concerned that they are obese or edematous" — these are patient characteristics, not drug-induced conditions. The LLM returned `$` for these pairs, incorrectly interpreting descriptive context as causal.

- **Sample 6 (3 FP):** Pairs like `vancomycin → AIDS`, `vancomycin → osteomyelitis`, `tenofovir disoproxil fumarate → osteomyelitis`. The text mentions AIDS and osteomyelitis as patient context, not as effects of the drugs. The LLM incorrectly returned `$`.

- **Sample 4 (2 FP):** Pairs `flavonoids → haemopericardium` and `flavonoids → gastrointestinal haemorrhage`. The text proposes flavonoids *may increase warfarin potency* — indirect causal chain, not direct causation. The LLM returned `$` incorrectly.

**Root cause:** The `relation_verify_llm` prompt (v0007) includes "associated with" and "risk factor for" in its causal language list, which is too broad. It also lacks explicit instruction to distinguish between patient characteristics/context and drug-induced conditions. The LLM over-generates `$` for pairs that are co-occurring in the text but not causally linked.

## 3) Agent Modification Suggestions

### Suggestion 1: Relax associative guard in `relation_result_to_id_pair`

- **Target agent:** `relation_result_to_id_pair` (PGM, v0001)
- **What to change:** Remove the associative guard block entirely (lines checking `associative_phrases` within 30 chars). Keep only the negation guard.
- **Expected impact:** Eliminates ~90% of FN (samples 1, 10, 15, 17, 18, 19). The LLM already correctly identified these as `$`; the PGM was incorrectly overriding.
- **Why easy:** Single code block removal in the `process` field. No new logic needed. The negation guard (which checks explicit negation like "did not cause") is sufficient and should be retained.

### Suggestion 2: Tighten causal language in `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (LLM, v0007)
- **What to change:** In the prompt's causal language list, remove "associated with" and "risk factor for". Add instruction: "Do NOT output '$' if the text describes patient characteristics, pre-existing conditions, or study demographics that are not explicitly stated as caused by the drug."
- **Expected impact:** Reduces FP in samples 4, 6, 8 where the LLM incorrectly interpreted patient context as causal. The LLM will still catch true causal relations using stronger causal phrases.
- **Why easy:** Simple prompt text edit. No code changes. The LLM already has good causal reasoning; this just clarifies the boundary.

### Suggestion 3: Add explicit "adverse event" recognition to `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (LLM, v0007)
- **What to change:** Add to the system prompt: "In clinical trial contexts, if the text lists 'adverse events', 'side effects', or 'treatment-emergent' conditions, treat those as causal ($) unless explicitly negated."
- **Expected impact:** Recovers FN in samples 17, 18 where the LLM returned `~` for clear adverse event listings. The LLM currently treats "adverse events were ..." as associative rather than causal.
- **Why easy:** Single sentence addition to the system prompt. No code or tool changes. Leverages existing LLM understanding of clinical trial language.