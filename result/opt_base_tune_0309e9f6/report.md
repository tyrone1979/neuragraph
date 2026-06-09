## 1) Metrics

### Overall Metrics

| Metric | Value |
|--------|-------|
| Samples | 20 |
| Total TP | 23 |
| Total FP | 5 |
| Total FN | 48 |
| Macro Precision | 0.50 |
| Macro Recall | 0.40 |
| Macro F1 | 0.42 |

### Per-Sample Metrics

| Sample | Precision | Recall | F1 | TP | FP | FN |
|--------|-----------|--------|----|----|----|----|
| 1 | 0.00 | 0.00 | 0.00 | 0 | 0 | 1 |
| 2 | 1.00 | 1.00 | 1.00 | 3 | 0 | 0 |
| 3 | 0.00 | 0.00 | 0.00 | 0 | 0 | 3 |
| 4 | 0.00 | 0.00 | 0.00 | 0 | 0 | 2 |
| 5 | 0.50 | 1.00 | 0.67 | 1 | 1 | 0 |
| 6 | 0.50 | 0.50 | 0.50 | 1 | 1 | 1 |
| 7 | 0.75 | 0.75 | 0.75 | 3 | 1 | 1 |
| 8 | 0.00 | 0.00 | 0.00 | 0 | 0 | 2 |
| 9 | 1.00 | 0.75 | 0.86 | 6 | 0 | 2 |
| 10 | 0.00 | 0.00 | 0.00 | 0 | 0 | 7 |
| 11 | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| 12 | 1.00 | 0.50 | 0.67 | 2 | 0 | 2 |
| 13 | 1.00 | 0.50 | 0.67 | 2 | 0 | 2 |
| 14 | 0.50 | 0.33 | 0.40 | 1 | 1 | 2 |
| 15 | 0.00 | 0.00 | 0.00 | 0 | 0 | 1 |
| 16 | 0.67 | 1.00 | 0.80 | 2 | 1 | 0 |
| 17 | 0.00 | 0.00 | 0.00 | 0 | 0 | 9 |
| 18 | 0.00 | 0.00 | 0.00 | 0 | 0 | 10 |
| 19 | 1.00 | 0.25 | 0.40 | 1 | 0 | 3 |
| 20 | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |

### Agent Version Mapping

| Graph ID | Agent ID | Version Used |
|----------|----------|--------------|
| wf_cid_re_llm_linear | ontology_hypernym_filter | current |
| wf_cid_re_llm_linear | cid_pair_generate | current |
| sg_cid_re_verify | relation_verify_llm | current |
| sg_cid_re_verify | relation_result_to_id_pair | current |

## 2) FN and FP Analysis

### False Negative Analysis (48 total FN)

**Primary Cause: LLM Over-Rejection of Causal Relations (Samples 1, 3, 4, 8, 10, 15, 17, 18)**

The `relation_verify_llm` agent returns `~` for many pairs that are true causal relations. The prompt instructs the LLM to only return `$` for explicit causal statements like "X caused Y", "X induced Y", "X resulted in Y", "X leads to Y". However, many biomedical articles describe causation using less explicit language (e.g., "associated with", "risk factor", "may cause", "can lead to", "due to", "implicated in", "result from"). The LLM is too strict, rejecting these as "co-occurrence, association, correlation, speculation".

- **Sample 1**: "propofol" causes "retrograde amnesia" – article describes amnesia during sedation with propofol, a clear causal context, but LLM returns `~`.
- **Sample 3**: "fluoxetine" causes "sexual dysfunction" – article explicitly studies "SSRI-induced female sexual dysfunction", but LLM returns `~`.
- **Sample 4**: "warfarin" causes "haemopericardium" – article states "fatal haemopericardium ... due to possible interaction of cranberry juice with warfarin", but LLM returns `~`.
- **Sample 8**: "furosemide" causes "hypokalemia" – article states "Diuretics may induce hypokalemia", but LLM returns `~`.
- **Sample 10**: "phenylpropanolamine" causes "Cerebral hemorrhage" – article states "PPA/caffeine can lead to cerebral hemorrhage", but LLM returns `~`.
- **Sample 17**: "bortezomib" causes "neuropathy" – article lists "neuropathy" as a frequent adverse event, but LLM returns `~`.
- **Sample 18**: "telmisartan" causes "edema" – article evaluates tolerability and lists adverse events, but LLM returns `~`.

**Secondary Cause: PGM Guard Override (Sample 14)**

The `relation_result_to_id_pair` PGM has a guard that checks for associative phrases within 100 characters of head/tail. In sample 14, the LLM correctly returned `$` for "zidovudine" → "megaloblastosis", but the guard overrode it to `[]` because the text contains "side effects" and "adverse effects" near the terms. This is a false negative caused by the guard being too aggressive.

**Tertiary Cause: Entity Filtering (Sample 15)**

In sample 15, the `ontology_hypernym_filter` agent removed "glaucoma" (D005901) but kept "open-angle glaucoma" (D005902) and "ocular hypertension" (D009798). The gold relation is "timolol" → "bradycardia", which is present in the pairs. However, the LLM returned `$` for "timolol" → "bradycardia", but the PGM guard may have overridden it (the text contains "reduction in mean heart rate" which is associative language). This is a false negative from the guard.

### False Positive Analysis (5 total FP)

**Primary Cause: LLM Over-Acceptance of Non-Causal Relations (Samples 5, 6, 7, 14, 16)**

The LLM returns `$` for pairs that are not causal in the context.

- **Sample 5**: "ouabain" → "left ventricular end-diastolic volume falls" – The article describes a study measuring the effect of ouabain on this parameter, but the relation is a measured outcome, not a causal adverse effect. The LLM incorrectly returns `$`.
- **Sample 6**: "tenofovir disoproxil fumarate" → "Fanconi syndrome" – The article states "Tenofovir has been implicated in the development of Fanconi syndrome", which is speculative ("implicated in"), but the LLM returns `$`.
- **Sample 7**: "norepinephrine" → "catatonia" – The article states "pretreatment with norepinephrine did not" increase catatonia, meaning norepinephrine does NOT cause catatonia, but the LLM returns `$`.
- **Sample 14**: "zidovudine" → "nausea" – The article lists nausea as a common side effect, but the LLM returns `$` for this pair. However, the PGM guard overrides it (associative phrase "side effects" nearby), so it becomes a false negative instead.
- **Sample 16**: "Prednisolone" → "tetanic" – The article describes prednisolone reducing tetanic tensions, not causing tetanic. The LLM incorrectly returns `$`.

## 3) Agent Modification Suggestions

### Suggestion 1: Relax `relation_verify_llm` Prompt to Accept Broader Causal Language

- **Target Agent ID**: `relation_verify_llm`
- **What to Change**: Prompt template (human message)
- **Change**: Expand the accepted causal patterns beyond the strict list. Add examples like "X is associated with Y", "X is a risk factor for Y", "X may cause Y", "X can lead to Y", "X results in Y", "X induces Y", "X is implicated in Y", "X is a side effect of Y", "X is an adverse effect of Y", "X due to Y", "X from Y". Keep the `~` for pre-existing conditions, co-occurrence without causal implication, speculation without evidence, or correlation without causal direction.
- **Expected Impact**: Reduce false negatives by 30-50% (samples 1, 3, 4, 8, 10, 17, 18 would likely improve). May slightly increase false positives, but the PGM guard can handle those.
- **Why Easy**: Single prompt edit in the agent meta. No code changes, no new tools, no external dependencies.

### Suggestion 2: Remove or Relax the Associative Phrase Guard in `relation_result_to_id_pair`

- **Target Agent ID**: `relation_result_to_id_pair`
- **What to Change**: PGM process code
- **Change**: Remove the associative phrase guard entirely, or change it to only override when the phrase is within 20 characters of the head/tail (instead of 100). The current 100-character window is too broad and catches many legitimate causal statements.
- **Expected Impact**: Eliminate false negatives caused by the guard (sample 14, and potentially samples 15, 19). May increase false positives slightly, but the LLM is already conservative.
- **Why Easy**: Single PGM code edit. No new tools or dependencies.

### Suggestion 3: Add a "Causal Signal" Check in `relation_result_to_id_pair` for `$` Results

- **Target Agent ID**: `relation_result_to_id_pair`
- **What to Change**: PGM process code
- **Change**: After the LLM returns `$`, add a lightweight check: if the text contains phrases like "did not", "no effect", "not associated", "not cause", "not induce", "not result in", "not lead to", "failed to", "unable to", "no evidence", "not significant" within 50 characters of the head or tail, override to `[]`. This catches cases where the LLM misreads negation (e.g., sample 7 where "norepinephrine did not" increase catatonia).
- **Expected Impact**: Reduce false positives from negation misreading (sample 7, and potentially others). This is a targeted fix for a specific failure mode.
- **Why Easy**: Single PGM code edit. Uses existing text and entity data. No new tools or dependencies.