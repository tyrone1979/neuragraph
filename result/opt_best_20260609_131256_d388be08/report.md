## 1) Metrics

**Overall Performance (500 samples)**

| Metric | Micro | Macro |
|--------|-------|-------|
| Precision | 0.4941 | 0.5809 |
| Recall | 0.8574 | 0.8664 |
| F1 | 0.6269 | 0.6510 |

**F1 Distribution (per-article)**
- Mean: 0.651, Std: 0.299
- Min: 0.0, Max: 1.0

**Error Totals**
- TP: 914, FP: 936, FN: 152

**Agent Version Mapping (effective)**

| Agent ID | Version Used |
|----------|-------------|
| relation_verify_llm | v0013 |
| relation_result_to_id_pair | v0003 |

## 2) FN and FP Analysis

**False Positive Analysis (10 highest-FP articles)**

The dominant FP pattern is **over-generation of relations from co-occurrence in drug combination/toxicity studies**. In articles where multiple drugs are administered as a combination regimen and adverse events are reported for the regimen as a whole, the LLM assigns `$` (induces) to each drug individually for every adverse event mentioned.

- **Sample 132** (39 FP): Article describes bilateral occlusion following injection of a *combination* of methylprednisolone acetate, lidocaine, epinephrine, or penicillin. The LLM outputs `$` for all 5 chemicals × 8 diseases = 40 pairs, when only the combination effect is described. The `relation_result_to_id_pair` PGM's causal override logic (checking for `{head}-induced {tail}` patterns) fails because the text uses "following the injection of...in combination with other drugs" rather than explicit `{head}-induced` phrasing.
- **Sample 453** (20 FP): HAART regimen article. 5 drugs (3TC, d4T, nevirapine, zidovudine, efavirenz) are each linked to all 4+ adverse events. The LLM applies Condition 3 ("if {head} is administered together with other chemical(s) as a combination/co-treatment regimen...answer '$'") too broadly—it assigns `$` to every drug in the regimen for every adverse event, even when the article attributes specific events to specific drugs (e.g., "NVP therapy was significantly associated with developing rash").
- **Samples 250, 344, 227, 441, 258, 433, 496, 467**: Same pattern—combination chemotherapy (cis-platinum/adriamycin/cyclophosphamide/hexamethylmelamine), drug interaction studies (cocaine/ethanol/cocaethylene), barium chloride effects, piperacillin/tazobactam, contrast media comparisons, quinine/quinidine comparisons, ACE inhibitor/spironolactone, heroin/methadone. In each case, the LLM assigns `$` to every chemical for every disease mentioned in the article, ignoring that the article is comparing multiple drugs or describing a combination effect.

**False Negative Analysis (10 highest-FN articles)**

FNs arise from two patterns:

1. **LLM over-application of Assumption 1.5** (rescue/resuscitation/antidote): In **Sample 50** (4 FN), pethidine-induced dysmetria and dysarthria are missed because the LLM applies Assumption 1.5 (head used as treatment for tail) incorrectly—pethidine is used for *pain*, not for dysmetria/dysarthria. The PGM's associative guard then blocks the remaining correct `$` outputs.
2. **LLM `~` output when causation is present**: In **Samples 407, 432, 370, 118, 104, 111, 62, 266, 500**, the LLM outputs `~` despite explicit causal language in the text. For example:
   - Sample 407: "HT significantly increased the risk of venous thromboembolism...stroke...breast cancer" → LLM outputs `~` for oestrogens/progestogens with these diseases.
   - Sample 432: "naproxen seemed to carry the highest risk for AMI/GI bleeding" → LLM outputs `~` for naproxen→toxicity.
   - Sample 62: "both agents are associated with significant hemodynamic side effects" → LLM outputs `~` for propofol→bradycardia.
   - Sample 500: "streptozotocin-induced cognitive deficits" → LLM outputs `~` for streptozotocin→cognitive deficits.

The `relation_result_to_id_pair` PGM's negation guard then blocks the remaining correct pairs because the associative phrase guard (checking for "associated with", "risk of", etc. within 15 chars) overrides the `$` output.

## 3) Agent Modification Suggestions

### Suggestion 1: Tighten LLM Condition 3 for combination regimens
- **Target agent**: `relation_verify_llm` (v0013)
- **What to change**: Modify Condition 3 in the prompt to require that the adverse event is *specifically attributed* to the individual drug, not just to the regimen. Add: "Only answer '$' for {head} if the text explicitly states or implies that {head} individually caused or contributed to {tail}, not merely because {head} was part of a combination regimen that caused {tail}."
- **Expected impact**: Reduces FP in combination therapy articles (samples 132, 453, 250, 344, 227, 441, 258, 433, 496, 467) by ~80% (estimated 700+ FP reduction).
- **Why easy**: Single prompt change to existing LLM agent. No new code, tools, or dependencies.

### Suggestion 2: Relax Assumption 1.5 to require explicit treatment relationship
- **Target agent**: `relation_verify_llm` (v0013)
- **What to change**: Modify Assumption 1.5 to require that {tail} is *explicitly* the condition being treated by {head}, not just any condition mentioned in the same article. Add: "Only apply this assumption if the text explicitly states that {head} is used as a treatment, therapy, or management for {tail} (e.g., '{head} is used to treat {tail}', '{head} therapy for {tail}')."
- **Expected impact**: Reduces FN in articles where a drug treats one condition but causes another (sample 50: pethidine treats pain but causes dysmetria).
- **Why easy**: Single prompt change to existing LLM agent.

### Suggestion 3: Remove associative guard from relation_result_to_id_pair PGM
- **Target agent**: `relation_result_to_id_pair` (v0003)
- **What to change**: Remove the "Relaxed associative guard" section (lines checking `associative_phrases` within 15 chars). The LLM already handles associative vs causal distinction in its prompt. The PGM guard is redundant and causes FN by overriding correct `$` outputs.
- **Expected impact**: Recovers FN in samples 407, 432, 370, 118, 104, 111, 62, 266, 500 (estimated 20+ FN reduction).
- **Why easy**: Simple PGM code deletion. No new logic needed.

### Suggestion 4: Strengthen causal override in relation_result_to_id_pair PGM
- **Target agent**: `relation_result_to_id_pair` (v0003)
- **What to change**: In the "Causal override" section, add `'{head} increased the risk of {tail}'` and `'{head} significantly increased the risk of {tail}'` to the `causal_patterns` list. These are common epidemiological causal phrasings that the current patterns miss.
- **Expected impact**: Recovers FN in samples 407, 432 where explicit "increased risk" language is used.
- **Why easy**: Simple string addition to existing PGM code.