## 1) Metrics

**Overall Performance (50 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.5858 | 0.5929 |
| Recall | 0.7447 | 0.7673 |
| F1 | 0.6557 | 0.6361 |

**Error Totals:** TP=140, FP=99, FN=48

**F1 Distribution:** mean=0.6361, std=0.297, min=0.0, max=1.0

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |

## 2) FN and FP Analysis

**False Positive Analysis**

The dominant FP pattern is **over-generation of CID relations for endogenous substances and supportive-care drugs** that the LLM incorrectly marks as `$` (induces). Key examples:

- **Sample 33 (16 FP):** `serotonin` (D012701) and `norepinephrine` (D009638) are predicted to induce all listed diseases (Serotonin syndrome, muscle rigidity, etc.). The text describes these as endogenous neurotransmitters whose *excessive stimulation* causes symptoms—the LLM fails to apply Assumption 1.6 (endogenous substance → `~`). Similarly, `diazepam` (D003975) is predicted to induce all diseases; the text states diazepam was given *as treatment* for the symptoms, violating Assumption 1.7 (supportive care → `~`).

- **Sample 15 (12 FP):** `angiotensin` (D000809) is predicted to induce ascites, abdominal pain, etc. The text discusses ACE inhibitor-induced angioedema—angiotensin is an endogenous peptide, not an administered drug. The LLM misses Assumption 1.6.

- **Sample 17 (10 FP):** All four chemotherapy agents (methotrexate, 5-fluorouracil, carmofur, capecitabine) are predicted to induce `leukaemia` (D007938). The text mentions leukaemia as the *condition being treated*, not an adverse effect. The LLM fails to recognize treatment context.

- **Sample 7 (5 FP):** `sodium`, `potassium`, `creatinine` (D012964, D011188, D003404) are predicted to induce renal damage. These are lab biomarkers, not drugs—Assumption 1.6 applies.

- **Sample 44 (6 FP):** `morphine` and `naloxone` are predicted to induce cystitis/visceral pain. The text describes morphine as *treatment* for CP-induced pain and naloxone as *antagonist*—both are therapeutic agents, not causal.

**False Negative Analysis**

FNs stem from **overly aggressive filtering by `relation_result_to_id_pair` PGM** and **LLM misses on true causal relations**:

- **Sample 12 (9 FN):** Only 1/10 true relations predicted. The text clearly states cisapride-diltiazem interaction causes QT prolongation, torsades, syncope. The `relation_result_to_id_pair` PGM's negation/associative guards likely override the LLM's `$` verdicts due to proximity of "reported after" or "caution be taken" phrases near entity mentions.

- **Sample 6 (4 FN):** Zero true relations predicted. The text states ifosfamide *causes* hemorrhagic cystitis and mesna *prevents* it. The LLM likely outputs `~` for ifosfamide→toxicity because mesna is discussed as prevention, confusing the causal direction.

- **Sample 24 (4 FN):** Zero true relations predicted. The text explicitly states ifosfamide causes hematuria, confusion, nausea, leukopenia. The `relation_result_to_id_pair` PGM's associative guard ("risk of", "may") likely overrides the LLM's `$` verdict.

- **Sample 42 (4 FN):** `telmisartan`→edema, cough, headache, dizziness, diarrhea are all missed. The text lists these as adverse events in the treatment group—clear causation. The LLM likely outputs `~` because these are common adverse events reported in a comparative trial, not explicitly stated as "induced by."

- **Sample 14 (3 FN):** `tacrolimus`→hepatotoxicity, PTLD, hemolytic anemia, pruritus missed. The text explicitly lists these as reasons for conversion from tacrolimus—clear causation. The `relation_result_to_id_pair` PGM's guards may override due to proximity of "conversion" or "discontinuation" language.

## 3) Agent Modification Suggestions

### Suggestion 1: Strengthen endogenous substance / supportive care detection in `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (v0010)
- **What to change:** Add a new Assumption 1.8 to the prompt: "if {head} is a sedative, muscle relaxant, analgesic, antidote, or supportive care (e.g. diazepam, morphine, naloxone) given to treat {tail}, answer '~'." (This already exists as 1.7 but is too narrow—extend to cover all therapeutic/antidote contexts.)
- **Expected impact:** Reduces FP by ~30-40% on samples 33, 44, 7, 15 where endogenous substances or therapeutic agents are incorrectly marked as causal.
- **Why easy:** Single prompt line addition; no code changes.

### Suggestion 2: Add treatment-context detection to `relation_result_to_id_pair` PGM

- **Target agent:** `relation_result_to_id_pair` (v0003)
- **What to change:** Add a PGM guard that checks if the text explicitly states the head entity is used to *treat* the tail entity (e.g., "for the treatment of {tail}", "{head} therapy for {tail}", "{head} was given to treat {tail}"). If found, override `$` to empty output.
- **Expected impact:** Reduces FP on samples 17 (leukaemia as treated condition), 44 (morphine/naloxone as treatment), 25 (NSAIDs as cause of urticaria when they are the suspected cause being tested).
- **Why easy:** Pure PGM string matching; no LLM calls.

### Suggestion 3: Relax associative guard proximity threshold in `relation_result_to_id_pair`

- **Target agent:** `relation_result_to_id_pair` (v0003)
- **What to change:** Increase the proximity threshold for associative phrase override from 15 characters to 5 characters, or remove the associative guard entirely and rely only on the negation guard.
- **Expected impact:** Reduces FN on samples 12, 24, 42 where associative phrases like "risk of", "may", "could" near entity mentions cause false overrides. The 15-char window is too aggressive—many true causal relations have associative language nearby.
- **Why easy:** Single numeric threshold change in PGM code.

### Suggestion 4: Add "treatment reversal" context detection to `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (v0010)
- **What to change:** Add a new condition: "if the text describes {head} as being given to *prevent*, *treat*, or *reverse* {tail} (e.g., '{head} to prevent {tail}', '{head} was given for {tail}'), answer '~'."
- **Expected impact:** Reduces FP on samples 6 (mesna prevents ifosfamide toxicity), 44 (morphine treats CP-induced pain), 33 (diazepam treats serotonin syndrome symptoms).
- **Why easy:** Single prompt line addition; no code changes.

### Suggestion 5: Add "adverse event reporting" context to `relation_verify_llm` prompt

- **Target agent:** `relation_verify_llm` (v0010)
- **What to change:** Add a new condition: "if the text reports adverse events in a clinical trial or case series where {tail} occurred in patients receiving {head} (e.g., '{tail} was reported in X% of patients receiving {head}', 'adverse events included {tail}'), answer '$'."
- **Expected impact:** Reduces FN on samples 42 (telmisartan adverse events), 35 (zidovudine adverse events), 45 (vancomycin adverse events) where clear causal reporting is missed.
- **Why easy:** Single prompt line addition; no code changes.