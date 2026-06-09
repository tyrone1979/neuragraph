## 1) Metrics

**Overall Metrics (50 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.5826 | 0.6103 |
| Recall | 0.7500 | 0.7570 |
| F1 | 0.6558 | 0.6418 |

**F1 Distribution (per-sample):** mean=0.6418, std=0.3079, min=0.0, max=1.0

**Error Totals:** TP=141, FP=101, FN=47

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |

## 2) FN and FP Analysis

**False Negative Analysis**

The 47 FNs are concentrated in articles where the LLM verifier (`relation_verify_llm`) outputs `~` (no relation) for true CID pairs. Key patterns from `examples_detail`:

- **Sample 12 (8 FN):** The article describes cisapride-diltiazem interaction causing QT prolongation. The LLM outputs `~` for pairs like `diltiazem → torsades de pointes` and `diltiazem → sudden cardiac death`. The text states "cisapride-diltiazem interaction" and "QT-interval prolongation" but the LLM likely applies Assumption 1.3 (physiological/grouping state) to diltiazem as a CYP3A4 inhibitor rather than causative agent, or fails to match Condition 3 (combination regimen adverse event).

- **Sample 6 (4 FN):** Article about ifosfamide-induced hemorrhagic cystitis. The LLM outputs `~` for `ifosfamide → emesis`. The text states "severe ifosfamide-induced emesis" — explicit causal language. The `relation_result_to_id_pair` PGM's negation guard may be overriding due to proximity of "without" or "prevent" near the terms.

- **Sample 14 (4 FN):** Tacrolimus side effects article. The LLM outputs `~` for `cyclosporine → pruritus`. The text lists pruritus as a side effect of tacrolimus, not cyclosporine — the LLM correctly rejects this pair. However, pairs like `tacrolimus → hepatotoxicity` and `tacrolimus → hemolytic anemia` are missing from output entirely, suggesting the hypernym filter or entity dedup removed relevant entities.

- **Sample 24 (4 FN):** Ifosfamide continuous infusion article. The LLM outputs `~` for `ifosfamide → confusion`, `ifosfamide → nausea`, `ifosfamide → leukopenia`. The text explicitly states "confusion (1), nausea (1), and Grade 2 leukopenia (1)" as nonurologic toxicity at 550 mg/m2/d. The LLM likely fails Condition 3 (combination/co-treatment) or applies Assumption 1.3 incorrectly.

**False Positive Analysis**

The 101 FPs are concentrated in articles where the LLM outputs `$` (causal) for non-causal associations. Key patterns:

- **Sample 33 (16 FP):** Serotonin syndrome article. The LLM outputs `$` for all chemical-disease pairs including `serotonin → thrombocytopenia`, `norepinephrine → rhabdomyolysis`, `diazepam → all diseases`. The text describes serotonin syndrome symptoms and treatment — diazepam is a treatment, not a cause. The LLM fails to apply Assumption 1.5 (rescue therapy/antidote) for diazepam.

- **Sample 17 (11 FP):** Chemotherapy leukoencephalopathy article. The LLM outputs `$` for `capecitabine → cytotoxic oedema` and all other pairs. The text describes leukoencephalopathy as a complication of multiple chemotherapy agents — the LLM correctly identifies causation but the gold standard may not include all these relations.

- **Sample 15 (10 FP):** ACE inhibitor angioedema article. The LLM outputs `$` for `angiotensin → ascites`. The text describes ACE inhibitor-induced angioedema — angiotensin is a physiological substance, not the administered drug. The LLM fails to apply Assumption 1.3 (physiological state).

- **Sample 7 (6 FP):** Contrast media nephropathy article. The LLM outputs `$` for `creatinine → congenital heart diseases`. Creatinine is a lab marker, not a causative agent. The LLM fails to identify creatinine as a non-drug entity.

**Root Cause Summary:** The primary failure mode is the LLM verifier's inability to distinguish between:
1. Physiological substances/lab markers vs. administered drugs (Assumption 1.3)
2. Treatment/rescue drugs vs. causative agents (Assumption 1.5)
3. Association vs. causation in combination therapy contexts (Condition 3)
4. The PGM negation guard in `relation_result_to_id_pair` may also be over-aggressive, overriding valid `$` outputs when negation phrases appear near terms.

## 3) Agent Modification Suggestions

### Suggestion 1: Improve LLM verifier's handling of physiological substances and lab markers

**Target Agent:** `relation_verify_llm` (v0010)

**What to Change:** Add a new Assumption in the prompt template (after 1.5) that explicitly instructs the model to identify and reject entities that are endogenous substances, lab biomarkers, or physiological parameters (e.g., creatinine, sodium, potassium, serotonin, norepinephrine, angiotensin, prostaglandin) when they appear as the `{head}` (chemical) in a CID pair, unless the text explicitly states they were administered as exogenous drugs.

**Expected Impact:** Reduces FPs in samples 7, 15, 16, 33, 5 where physiological substances are incorrectly identified as causative agents. Estimated FP reduction: 15-25.

**Why Easy:** Single prompt addition — no code changes, no new tools, no external dependencies. The pattern is clear from examples_detail (creatinine, angiotensin, serotonin, norepinephrine, prostaglandin all cause FPs).

### Suggestion 2: Strengthen treatment/rescue drug detection in LLM verifier

**Target Agent:** `relation_verify_llm` (v0010)

**What to Change:** Expand Assumption 1.5 to explicitly include sedatives, muscle relaxants, and supportive care medications (e.g., diazepam, morphine, naloxone) as treatment/rescue drugs. Add clarifying language: "if {head} is administered as a treatment, antidote, rescue therapy, or supportive care for {tail} or for any condition mentioned in the article, answer '~'."

**Expected Impact:** Reduces FPs in sample 33 (diazepam → all diseases), sample 44 (morphine/naloxone → cystitis/edema). Estimated FP reduction: 10-15.

**Why Easy:** Single prompt modification — no code changes. The pattern is clear: diazepam is given for muscle rigidity/seizures, morphine for pain, naloxone as antidote.

### Suggestion 3: Fix PGM negation guard overrides in relation_result_to_id_pair

**Target Agent:** `relation_result_to_id_pair` (v0003)

**What to Change:** In the PGM code, modify the negation guard to require the negation phrase to be within 30 characters of BOTH head and tail terms simultaneously, not just one. Currently, the guard triggers if a negation phrase is within 50 chars of EITHER head or tail. Change the logic to require proximity to both terms.

**Expected Impact:** Reduces FNs where valid causal relations are incorrectly suppressed. Sample 6 (ifosfamide → emesis) may be recovered — the text "without impairment" is near "ifosfamide" but not near "emesis". Estimated FN reduction: 3-5.

**Why Easy:** Single-line change in PGM code — change `if abs(idx - tidx) <= 50` to require both head and tail proximity, or increase the distance threshold to 100 for the combined check.

### Suggestion 4: Improve LLM verifier's handling of combination therapy adverse events

**Target Agent:** `relation_verify_llm` (v0010)

**What to Change:** In Condition 3, add clarifying language that when {head} is part of a combination/co-treatment regimen and {tail} is reported as an adverse event in patients receiving that regimen, the model should answer '$' even if the text attributes the event to the combination rather than {head} alone. Add: "This includes cases where {head} is one component of a multi-drug regimen and {tail} is listed as a toxicity or adverse reaction in the study population."

**Expected Impact:** Reduces FNs in sample 12 (diltiazem → QT prolongation/torsades), sample 24 (ifosfamide → confusion/nausea/leukopenia). Estimated FN reduction: 5-8.

**Why Easy:** Single prompt modification — no code changes. The pattern is clear from examples_detail where combination therapy adverse events are missed.