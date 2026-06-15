## 1) Metrics

| Metric | Value |
|--------|-------|
| Experiment ID | c17f8d7e-739a-47b2-8dad-4264b67b713e |
| Graph | sg_e2e_pubtator_re |
| Dataset | regression_2_gold_test.csv |
| Sample Count | 2 |
| Report Mode | table |
| Status | completed |

**Agent Version Mapping**

| Agent ID | Version Used |
|----------|-------------|
| relation_extract_pubtator | current |

**Per-Sample Results**

| Sample ID | Text | Relations Extracted |
|-----------|------|-------------------|
| 1 | Aspirin may reduce the risk of heart disease. | D000068799 \| CID \| D054058, D000069552 \| CID \| D050197, D001241 \| CID \| D054058, D000069552 \| CID \| D054058, D000068799 \| CID \| D002545, D000077144 \| CID \| D054058 |
| 2 | Metformin is commonly used to treat type 2 diabetes. | C529054 \| CID \| D051436, C020269 \| CID \| D051436, C529054 \| CID \| D007328, C529054 \| CID \| D003924, C529054 \| CID \| D003920 |

**Note:** No gold standard labels are available in the provided package, so precision, recall, and F1 cannot be computed. The metrics_summary is empty (sample_count: 0). The report contains only extracted relations per sample.

## 2) FN and FP Analysis

**False Negative Analysis:**
- Sample 1 ("Aspirin may reduce the risk of heart disease"): The extracted relations include multiple CID pairs (e.g., D000068799→D054058, D001241→D054058, D000069552→D050197, D000068799→D002545, D000077144→D054058). Without gold labels, it is unclear which relations are correct. However, the text mentions only "Aspirin" and "heart disease" – the extracted entities appear to include many unrelated MeSH IDs (e.g., D054058 appears 3 times, D050197, D002545, D077144). This suggests the PubTator API is returning relations for entities not explicitly mentioned in the text or over-expanding entity recognition.
- Sample 2 ("Metformin is commonly used to treat type 2 diabetes"): Extracted relations include C529054→D051436, C020269→D051436, C529054→D007328, C529054→D003924, C529054→D003920. The text mentions only "Metformin" and "type 2 diabetes". The entity C529054 (likely Metformin) appears in 4 relations, but the target disease "type 2 diabetes" (D003922) is not present in any relation. Instead, D051436 (Diabetes Mellitus), D007328 (Insulin Resistance), D003924 (Diabetes Mellitus, Type 1), D003920 (Diabetes Mellitus, Experimental) are returned. This indicates the PubTator API is mapping "type 2 diabetes" to broader or incorrect disease concepts.

**False Positive Analysis:**
- Without gold labels, definitive FP identification is impossible. However, the high number of relations per sample (6 and 5) for short, simple sentences suggests over-generation. The PubTator API appears to return all possible CID relations for all recognized entities, including many that are not semantically related to the text's main message.

**Likely Causes:**
1. **PubTator API over-generation:** The `PubTatorRelationExtractor` plugin returns all relations found by PubTator3 without filtering for relevance to the input text's main entities.
2. **Entity normalization issues:** The API maps surface forms to MeSH IDs but may use overly broad mappings (e.g., "heart disease" → multiple IDs, "type 2 diabetes" → D051436 instead of D003922).
3. **No post-processing:** The PGM code passes raw API output directly to `__result__` without any filtering, deduplication, or relevance scoring.

## 3) Agent Modification Suggestions

### Suggestion 1: Add relation relevance filtering in `relation_extract_pubtator`

- **Target Agent:** `relation_extract_pubtator`
- **What to Change:** Add post-processing logic in the PGM code after `pt.extract_relations()` to filter relations based on entity overlap with input entities.
- **Change Details:** After receiving `__result__`, filter to keep only relations where both head and tail entity IDs appear in the `entities` dictionary provided as input. This ensures only relations involving entities explicitly recognized in the text are kept.
- **Expected Impact:** Reduces FP by eliminating relations for entities not present in the input text. For Sample 1, this would remove relations involving D054058 (if not in input entities) and D050197, D002545, D077144. For Sample 2, it would remove relations involving D007328, D003924, D003920 if those entities are not in the input.
- **Why Easy:** Single code change in the existing PGM block. No new dependencies. Uses existing `entities` input that is already passed to the agent.

### Suggestion 2: Add deduplication of relations in `relation_extract_pubtator`

- **Target Agent:** `relation_extract_pubtator`
- **What to Change:** Add deduplication logic after relation extraction to remove duplicate `head_id | CID | tail_id` triples.
- **Change Details:** Convert `__result__` to a set of tuples before returning as a list. This removes exact duplicates (e.g., D000069552 | CID | D054058 appearing twice in Sample 1).
- **Expected Impact:** Reduces redundant relations, making output cleaner and potentially improving downstream metrics if duplicates are counted as separate predictions.
- **Why Easy:** Single line change: `__result__ = list(set(__result__))` after the extraction call.

### Suggestion 3: Add entity ID normalization using input entities

- **Target Agent:** `relation_extract_pubtator`
- **What to Change:** Add a normalization step that maps PubTator API entity IDs to the canonical IDs present in the input `entities` dictionary.
- **Change Details:** After extraction, for each relation, check if the head or tail ID is a synonym/alternate ID for an entity in the input `entities` dict. If so, replace with the canonical ID from input entities. This addresses the "type 2 diabetes" → D051436 vs D003922 mismatch.
- **Expected Impact:** Reduces FN by ensuring relations are counted against the correct gold entity IDs. For Sample 2, D051436 would be mapped to D003922 if the input entities contain that mapping.
- **Why Easy:** Uses existing `entities` input. Can be implemented as a simple dictionary lookup/mapping within the PGM code. No external API calls needed.