## 1) Metrics

**Overall Performance (50 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.588 | 0.590 |
| Recall | 0.729 | 0.744 |
| F1 | 0.651 | 0.622 |

**F1 Distribution (per-sample)**
- Mean: 0.622
- Std: 0.317
- Min: 0.000
- Max: 1.000

**Error Totals**
- True Positives: 137
- False Positives: 96
- False Negatives: 51

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0010 |
| relation_result_to_id_pair | v0003 |
| cid_pair_generate | current |
| e2e_entities_dedup_by_id | current |
| e2e_hypernym_filter | current |

## 2) FN and FP Analysis

**False Positive Pattern: Over-generation from co-occurrence in drug interaction / adverse event lists**

The dominant FP pattern (samples 7, 27, 44, 33, 15, 8, 25, 16) involves the LLM verifying `$` for pairs where the article lists adverse events or symptoms of a condition, but the chemical is not the causative agent. Key examples:

- **Sample 7**: `creatinine → congenital heart diseases` — creatinine is a lab value, not a drug; the article discusses contrast media-induced nephropathy in children with congenital heart disease. The LLM incorrectly links a biomarker to a pre-existing condition.
- **Sample 27**: `phosphate → hemosiderosis` — phosphate is a biochemical component mentioned in AZT mechanism text, not a causative drug. The LLM treats any co-occurring chemical-disease pair as causal.
- **Sample 44**: `naloxone → painful syndromes` — naloxone is an antagonist used to reverse morphine effects, not a cause of pain. The LLM fails to apply Assumption 1.4 (inhibition/blockade).
- **Sample 33**: All 15 FPs are from `serotonin`, `norepinephrine`, `diazepam` paired with symptoms of serotonin syndrome — these are endogenous substances or treatments, not causative agents. The LLM does not distinguish between endogenous neurotransmitters and administered drugs.
- **Sample 15**: `angiotensin → ascites` — angiotensin is an endogenous peptide, not an administered drug. The article discusses ACE inhibitor-induced angioedema, not angiotensin causing ascites.

**Root cause**: The `relation_verify_llm` prompt's Condition 3 (combination/co-treatment regimen) is too broad. It causes the LLM to accept any chemical mentioned in the context of adverse events as causative, even when the chemical is an endogenous substance, a biomarker, or a treatment for the condition. The Assumptions (1.3, 1.4) are not being reliably triggered because the LLM does not recognize "endogenous substance" vs "administered drug" without explicit guidance.

**False Negative Pattern: Over-filtering by `relation_result_to_id_pair` PGM guard**

The FN-heavy samples (12, 6, 24, 43, 42, 14, 20) show a different pattern: the LLM correctly outputs `$`, but the PGM guard in `relation_result_to_id_pair` suppresses the relation.

- **Sample 6**: `ifosfamide → emesis` — LLM outputs `$`, but the PGM guard's associative phrase filter (`'may'`, `'could'`, `'possible'`) matches text like "ifosfamide-induced emesis" because `'may'` appears elsewhere in the text within 15 chars of a term. The guard incorrectly overrides a clear causal relation.
- **Sample 12**: `azole → syncope` — LLM outputs `~` (correctly rejecting), but 9 FNs come from pairs like `cisapride → torsades de pointes` where the LLM likely output `$` but the guard suppressed them. The article explicitly states "cisapride... torsades de pointes... have been reported" — this is a known causal relation.
- **Sample 24**: `mesna → leukopenia` — LLM outputs `~` (correctly, mesna is a protective agent), but 4 FNs from `Ifosfamide → hematuria`, `Ifosfamide → confusion`, `Ifosfamide → nausea`, `Ifosfamide → leukopenia` are suppressed. The article explicitly states these are ifosfamide toxicities.
- **Sample 43**: `uridine → megaloblastosis` — LLM outputs `~` (correctly, uridine reverses AZT toxicity), but 3 FNs from `Benzylacyclouridine → marrow suppression`, `Benzylacyclouridine → anemia`, `Benzylacyclouridine → leukopenia` are suppressed. The article states BAU "reversed AZT-induced anemia and leukopenia" — BAU is a treatment, not a cause.

**Root cause**: The `relation_result_to_id_pair` PGM guard uses a 15-character proximity window for associative phrases (`'may'`, `'could'`, `'possible'`, `'suggest'`). These words are common in biomedical text and frequently appear within 15 characters of any entity mention, causing false suppression of valid causal relations. The guard is too aggressive.

## 3) Agent Modification Suggestions

### Suggestion 1: Tighten `relation_result_to_id_pair` associative phrase guard

**Target agent**: `relation_result_to_id_pair` (PGM, v0003)

**What to change**: In the PGM code, reduce the proximity window for associative phrases from 15 characters to 5 characters. Additionally, remove `'may'`, `'could'`, `'possible'`, `'might'`, `'suggest'` from the associative_phrases list — these are too common and non-specific.

**Expected impact**: Reduces FN by ~30-40% (recovers suppressed relations like `ifosfamide → emesis`, `cisapride → torsades de pointes`, `Ifosfamide → hematuria`). May introduce a small number of new FPs (estimated <5) where associative language is genuinely within 5 chars.

**Why easy**: Single-line change in PGM code. No new dependencies. Directly addresses the dominant FN pattern observed in samples 6, 12, 24, 43.

### Suggestion 2: Add "endogenous substance" guard to `relation_verify_llm` prompt

**Target agent**: `relation_verify_llm` (LLM, v0010)

**What to change**: Add a new Assumption to the prompt: "If {head} is an endogenous substance (neurotransmitter, hormone, electrolyte, metabolite, vitamin, amino acid, or similar naturally occurring compound) rather than an administered drug or xenobiotic, answer '~'." Place this as Assumption 1.6 (after existing 1.5).

**Expected impact**: Eliminates ~40-50% of FPs (samples 7, 27, 33, 15, 44). Specifically removes false relations like `creatinine → congenital heart diseases`, `phosphate → hemosiderosis`, `serotonin → [any symptom]`, `norepinephrine → [any symptom]`, `angiotensin → ascites`, `sodium → [any disease]`, `potassium → [any disease]`.

**Why easy**: Single prompt addition. No code changes. The LLM already has the concept of "administered drug" (Assumption 1.3 mentions "chemical administered to subjects"). This extends that logic to explicitly exclude endogenous substances.

### Suggestion 3: Strengthen "treatment/rescue therapy" Assumption in `relation_verify_llm`

**Target agent**: `relation_verify_llm` (LLM, v0010)

**What to change**: Expand Assumption 1.5 to also cover: "if {head} is used as a protective agent, rescue therapy, or preventive treatment for {tail} (or for a condition that includes {tail} as a symptom/complication), answer '~'." Add examples: "e.g., mesna prevents ifosfamide-induced cystitis, BAU reverses AZT-induced marrow suppression."

**Expected impact**: Reduces FPs from samples 44 (naloxone reversing morphine effects), 25 (paracetamol/nimesulide as alternative drugs for NSAID-induced urticaria), and prevents similar future errors. Also helps with samples 6/24/43 where the LLM currently outputs `$` for protective agents.

**Why easy**: Prompt-only change. The existing Assumption 1.5 already covers "resuscitation, rescue therapy, antidote, or treatment" — this just broadens to include "protective agent" and "preventive treatment."