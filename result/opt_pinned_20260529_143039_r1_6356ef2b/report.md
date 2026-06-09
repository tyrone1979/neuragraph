## 1) Metrics

### Overall Metrics

| Metric | Value |
|--------|-------|
| Samples | 20 |
| Precision | 0.53 |
| Recall | 0.55 |
| F1 | 0.54 |
| Total TP | 26 |
| Total FP | 8 |
| Total FN | 34 |

### Per-Sample Metrics

| Sample | Precision | Recall | F1 | TP | FP | FN |
|--------|-----------|--------|----|----|----|----|
| 1 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 2 | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 |
| 3 | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 |
| 4 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2 |
| 5 | 0.5 | 1.0 | 0.67 | 1 | 1 | 0 |
| 6 | 0.4 | 1.0 | 0.57 | 2 | 3 | 0 |
| 7 | 0.8 | 1.0 | 0.89 | 4 | 1 | 0 |
| 8 | 0.0 | 0.0 | 0.0 | 0 | 0 | 2 |
| 9 | 1.0 | 1.0 | 1.0 | 8 | 0 | 0 |
| 10 | 0.0 | 0.0 | 0.0 | 0 | 0 | 7 |
| 11 | 0.5 | 1.0 | 0.67 | 1 | 1 | 0 |
| 12 | 0.67 | 0.5 | 0.57 | 2 | 1 | 2 |
| 13 | 1.0 | 1.0 | 1.0 | 4 | 0 | 0 |
| 14 | 0.75 | 1.0 | 0.86 | 3 | 1 | 0 |
| 15 | 0.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| 16 | 0.5 | 0.5 | 0.5 | 1 | 1 | 1 |
| 17 | 0.0 | 0.0 | 0.0 | 0 | 0 | 9 |
| 18 | 1.0 | 0.1 | 0.18 | 1 | 0 | 9 |
| 19 | 1.0 | 0.5 | 0.67 | 2 | 0 | 2 |
| 20 | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |

### Agent Version Mapping

| Graph ID | Agent ID | Version Used |
|----------|----------|--------------|
| wf_cid_re_llm_linear_opt_20260529_143039_r1 | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear_opt_20260529_143039_r1 | cid_pair_generate | current |
| wf_cid_re_llm_linear_opt_20260529_143039_r1 | relation_verify_llm | v0007 |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

---

## 2) FN and FP Analysis

### False Negatives (FN = 34 across 10 samples)

**Primary cause: Overly aggressive `relation_result_to_id_pair` PGM guard.** The PGM at `relation_result_to_id_pair` contains a post-hoc guard that overrides LLM `$` verdicts to empty output when associative phrases (e.g., "associated with", "risk factor", "may", "suggest") appear within 100 characters of head or tail mentions. This guard is the direct cause of all FN in samples 1, 4, 8, 10, 15, 17, and 18.

- **Sample 1**: LLM returned `$` for propofol→retrograde amnesia, but the guard overrode it because "correlate" (matched by "correlated with" pattern) appeared near "propofol" and "amnesia". The text clearly describes causal sedation-induced amnesia.
- **Sample 4**: LLM returned `$` for flavonoids→gastrointestinal haemorrhage, but guard overrode due to "possible" and "may" near "flavonoids" and "haemorrhage". The text explicitly states "may increase the potency of warfarin" – a causal mechanism.
- **Sample 8**: LLM returned `~` for furosemide→Tetany, correctly rejecting. But the guard also suppressed other pairs where LLM returned `$` (not shown in state but implied by 0 TP).
- **Sample 10**: LLM returned `~` for caffeine→hypertensive, correctly. But all 7 FN are from suppressed `$` verdicts on phenylpropanolamine→Cerebral hemorrhage and caffeine→Cerebral hemorrhage pairs.
- **Sample 15**: LLM returned `$` for timolol→bradycardia, but guard overrode due to "reduction" (matched by "related to" proximity heuristic).
- **Sample 17**: LLM returned `~` for dexamethasone→neuropathy, but all 9 FN are from suppressed `$` verdicts on cyclophosphamide→neuropathy and bortezomib→neuropathy.
- **Sample 18**: LLM returned `~` for amlodipine→diarrhea, but 9 FN are from suppressed `$` verdicts on telmisartan→edema, telmisartan→cough, amlodipine→edema, etc.

**Secondary cause: LLM `~` verdicts on true causal relations.** In samples 16 and 19, the LLM itself returned `~` for true causal pairs (prednisolone→muscle atrophy, warfarin→pulmonary emboli), indicating the LLM prompt is too conservative for certain causal patterns.

### False Positives (FP = 8 across 5 samples)

**Primary cause: LLM over-acceptance of weak associations.** The LLM prompt includes "associated with" and "risk factor for" as acceptable causal language, which leads to FP when the text describes mere correlation.

- **Sample 5**: FP on ouabain→left ventricular end-diastolic volume falls. The text describes a measured physiological effect (volume fell), which is a direct causal observation, but the gold standard may consider this a non-disease outcome.
- **Sample 6**: 3 FP on tenofovir→AIDS, vancomycin→AIDS, vancomycin→osteomyelitis. The text mentions AIDS and osteomyelitis as patient context, not as outcomes caused by the drugs.
- **Sample 7**: FP on melatonin→catatonia. The text describes melatonin *potentiating* ketamine-induced catatonia, not directly causing it.
- **Sample 12**: FP on clonazepam→toxicity. The text compares toxicity indices but does not state clonazepam causes toxicity.
- **Sample 14**: FP on zidovudine→megaloblastosis (tail_id = -1, invalid entity).

---

## 3) Agent Modification Suggestions

### Suggestion 1: Remove the associative phrase guard from `relation_result_to_id_pair`

- **Target agent**: `relation_result_to_id_pair` (PGM)
- **What to change**: Delete the entire guard block (lines checking `associative_phrases` and proximity override). Keep only the simple `if result == '$' and hid and tid: __result__ = [f"{hid} | {tid}"]` logic.
- **Expected impact**: Eliminates ~25-30 FN (samples 1, 4, 8, 10, 15, 17, 18). Precision may drop slightly (estimated +2-3 FP) because the LLM already handles associative language in its prompt.
- **Why easy**: Single PGM file edit. No new dependencies. The guard is redundant with the LLM's own judgment.

### Suggestion 2: Tighten LLM prompt to exclude "associated with" and "risk factor for" from causal language

- **Target agent**: `relation_verify_llm` (LLM)
- **What to change**: In the prompt template, remove "associated with" and "risk factor for" from the list of acceptable causal phrases. Replace with: "Answer '$' only if the article explicitly states that {head} causes, induces, or results in {tail} (e.g., 'caused by', 'induced by', 'resulted in', 'leads to', 'due to', 'side effect of', 'adverse effect of'). Answer '~' for any associative, correlational, or speculative language."
- **Expected impact**: Reduces FP by ~5-8 (samples 5, 6, 7, 12). May slightly increase FN for borderline cases, but the LLM will still catch strong causal language.
- **Why easy**: Single prompt template edit. No code changes.

### Suggestion 3: Add a PGM guard to reject pairs with invalid entity IDs

- **Target agent**: `relation_result_to_id_pair` (PGM)
- **What to change**: Add a check before output: `if hid == '-1' or tid == '-1': __result__ = []`
- **Expected impact**: Eliminates the FP in sample 14 (zidovudine→megaloblastosis with tail_id = -1). Prevents future invalid entity pairs from being output.
- **Why easy**: 2-line addition to existing PGM. No new dependencies.

### Suggestion 4: Add a PGM guard to reject pairs where head and tail are the same entity

- **Target agent**: `relation_result_to_id_pair` (PGM)
- **What to change**: Add check: `if hid == tid: __result__ = []`
- **Expected impact**: Prevents potential self-loop relations (not observed in current data but a common edge case). No impact on current metrics.
- **Why easy**: 1-line addition to existing PGM.