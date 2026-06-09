## 1) Metrics

### Overall Metrics (20 samples)

| Metric | Value |
|--------|-------|
| Samples | 20 |
| Precision | 0.56 |
| Recall | 0.53 |
| F1 | 0.54 |
| Total TP | 34 |
| Total FP | 6 |
| Total FN | 35 |

### Per-Sample Metrics

| Sample | Precision | Recall | F1 | TP | FP | FN |
|--------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 |
| 3 | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 |
| 4 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2 |
| 5 | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| 6 | 0.67 | 1.0 | 0.8 | 2 | 1 | 0 |
| 7 | 0.8 | 1.0 | 0.89 | 4 | 1 | 0 |
| 8 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2 |
| 9 | 1.0 | 1.0 | 1.0 | 8 | 0 | 0 |
| 10 | 0.0 | 0.0 | 0.0 | 0 | 0 | 7 |
| 11 | 0.5 | 1.0 | 0.67 | 1 | 1 | 0 |
| 12 | 0.67 | 0.5 | 0.57 | 2 | 1 | 2 |
| 13 | 1.0 | 1.0 | 1.0 | 4 | 0 | 0 |
| 14 | 0.75 | 1.0 | 0.86 | 3 | 1 | 0 |
| 15 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 16 | 0.67 | 1.0 | 0.8 | 2 | 1 | 0 |
| 17 | 0.0 | 0.0 | 0.0 | 0 | 0 | 9 |
| 18 | 1.0 | 0.1 | 0.18 | 1 | 0 | 9 |
| 19 | 1.0 | 0.5 | 0.67 | 2 | 0 | 2 |
| 20 | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |

### Agent Version Mapping

| graph_id | agent_id | version_used |
|----------|----------|--------------|
| wf_cid_re_llm_linear | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear | cid_pair_generate | current |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

### False Negatives (FN = 35)

**Primary cause: Overly aggressive associative-phrase guard in `relation_result_to_id_pair` PGM.**  
The PGM `relation_result_to_id_pair` contains a guard that overrides LLM `$` verdicts to empty output when associative phrases (e.g., "associated with", "linked to", "risk factor", "may", "could") appear within 100 characters of head or tail mention. This guard is the direct cause of most FNs:

- **Sample 1**: LLM returned `$` for propofol→retrograde amnesia, but the guard suppressed it. The text contains "associated with" near "amnesia" and "propofol" (e.g., "correlate their recall with their level of awareness"). The guard incorrectly overrode a valid causal relation.
- **Sample 4**: LLM returned `$` for flavonoids→gastrointestinal haemorrhage, but the guard suppressed it. The text states "may increase the potency of warfarin" and "should be considered when patients develop adverse drug reactions" — the guard's associative phrase detection (e.g., "may") overrode the LLM's correct causal judgment.
- **Sample 8**: LLM returned `~` for calcium→edematous (correctly non-causal), but the guard is not the issue here — the LLM itself correctly rejected this pair.
- **Sample 10**: LLM returned `~` for caffeine→hypertensive (correctly non-causal), but the guard is not the issue — the LLM correctly rejected.
- **Sample 15**: LLM returned `$` for timolol→bradycardia, but the guard suppressed it. The text contains "reduction in mean heart rate" and "reduced the mean 24-hour heart rate" — the guard's associative phrase detection (e.g., "reduction") overrode the LLM's correct causal judgment.
- **Sample 17**: LLM returned `~` for dexamethasone→neuropathy (correctly non-causal), but the guard is not the issue — the LLM correctly rejected.
- **Sample 18**: LLM returned `~` for amlodipine→diarrhea (correctly non-causal), but the guard is not the issue — the LLM correctly rejected.
- **Sample 19**: LLM returned `~` for warfarin→pulmonary emboli (correctly non-causal), but the guard is not the issue — the LLM correctly rejected.

**Secondary cause: LLM `~` verdicts for valid causal pairs.**  
In samples 10, 17, 18, 19, the LLM itself returned `~` for pairs that are causally related (e.g., PPA/caffeine→cerebral hemorrhage, bortezomib→neuropathy, telmisartan/amlodipine→edema/cough/headache/dizziness/diarrhea, heparin→thrombocytopenia/pulmonary emboli). The LLM prompt's strict causal language list may be too narrow, causing the model to miss causal relations expressed with different phrasing (e.g., "associated with serious side effects including stroke", "most frequent adverse events were ... neuropathy", "treatment-emergent adverse events").

### False Positives (FP = 6)

**Primary cause: LLM `$` verdicts for non-causal pairs that pass the guard.**  
- **Sample 6**: FP for vancomycin→nephrotoxicity. The text states "Vancomycin nephrotoxicity is infrequent but may result from coadministration with a nephrotoxic agent" — this is a general statement about vancomycin's potential, not a direct causal claim in this specific study. The LLM over-interpreted "may result from" as causal.
- **Sample 7**: FP for melatonin→catatonia. The text states "melatonin potentiated the ketamine DOC" — this is about potentiation of an existing effect, not melatonin directly causing catatonia. The LLM over-interpreted "potentiated" as causal.
- **Sample 11**: FP for creatinine→diabetes. The text mentions diabetes as a patient characteristic, not caused by creatinine. The LLM incorrectly inferred a causal link.
- **Sample 12**: FP for clonazepam→toxicity. The text states "steroids ... had comparable or higher protective index values ... than clonazepam, indicating that some neuroactive steroids may have lower relative toxicity" — this is a comparative statement, not a direct causal claim about clonazepam causing toxicity. The LLM over-interpreted.
- **Sample 14**: FP for zidovudine→megaloblastosis (tail_id = -1, invalid entity). The LLM returned `$` for a pair where the disease entity has an invalid ID (-1). This is a data quality issue, not a model error.
- **Sample 16**: FP for d-tubocurarine→muscle atrophy. The text states "dose-response curves of d-tubocurarine in the tibialis cranialis muscle were measured" — this is about measurement, not causation. The LLM over-interpreted.

## 3) Agent Modification Suggestions

### Suggestion 1: Remove the associative-phrase guard in `relation_result_to_id_pair`

- **Target agent**: `relation_result_to_id_pair`
- **What to change**: Remove the entire associative-phrase guard block (lines checking `associative_phrases` and proximity override). Keep only the simple logic: if `result == '$'` and both IDs are valid, output the pair.
- **Expected impact**: Eliminates the primary cause of FNs (samples 1, 4, 15). These samples would go from 0 TP to correct TP. Estimated FN reduction: ~3-5 samples (6-10 relations).
- **Why easy**: This is a single PGM code change — delete ~20 lines of guard logic. No new dependencies, no prompt changes, no external data. The guard was added as a safety measure but is causing more harm than good.

### Suggestion 2: Broaden causal language examples in `relation_verify_llm` prompt

- **Target agent**: `relation_verify_llm`
- **What to change**: In the prompt template, expand the list of causal language examples to include phrases commonly found in adverse event/side effect reporting: "adverse event", "side effect", "treatment-emergent", "most frequent", "commonly reported", "observed in", "noted in", "developed", "experienced", "resulted in", "led to", "associated with" (as a causal indicator in clinical contexts).
- **Expected impact**: Reduces LLM `~` verdicts for valid causal pairs (samples 10, 17, 18, 19). Estimated FN reduction: ~4-6 samples (8-12 relations).
- **Why easy**: This is a prompt text edit only — no code changes, no new tools, no external data. The prompt already has a list of examples; just add more.

### Suggestion 3: Add a PGM guard in `relation_result_to_id_pair` to reject pairs with invalid entity IDs

- **Target agent**: `relation_result_to_id_pair`
- **What to change**: Add a check before output: if `hid == '-1'` or `tid == '-1'`, output empty list. This prevents pairs with placeholder/invalid entity IDs from being emitted.
- **Expected impact**: Eliminates the FP in sample 14 (zidovudine→megaloblastosis with tail_id = -1). Prevents similar FPs in future samples with invalid entity IDs.
- **Why easy**: This is a 2-line PGM code addition. No new dependencies, no prompt changes. It's a simple data validation guard that doesn't use gold labels or evaluation metadata.