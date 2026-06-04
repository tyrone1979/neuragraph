"""
BASELINE RE REPORT + Optimized F1 Prediction
==============================================
"""
import json

s = json.loads(open('result/c422b97c-be21-4b6a-968c-c4994229d702/states.json', encoding='utf-8').read())
ks = sorted([int(k) for k in s if k.isdigit()])

rows = []
for k in ks:
    m = s[str(k)].get('metrics', {})
    tp = int(m.get('rel_tp', 0))
    fp = int(m.get('rel_fp', 0))
    fn = int(m.get('rel_fn', 0))
    pairs = s[str(k)].get('pairs', [])
    relations = s[str(k)].get('relations', [])
    text = (s[str(k)].get('text', '') or '')[:200]
    rows.append({
        'idx': k, 'tp': tp, 'fp': fp, 'fn': fn,
        'error_impact': fp + fn,
        'n_pairs': len(pairs),
        'n_predicted': len(relations),
        'text_preview': text,
    })

mtp = sum(r['tp'] for r in rows)
mfp = sum(r['fp'] for r in rows)
mfn = sum(r['fn'] for r in rows)
mip = mtp / (mtp + mfp) if mtp + mfp else 0
mir = mtp / (mtp + mfn) if mtp + mfn else 0
mif = 2 * mip * mir / (mip + mir) if mip + mir else 0

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f = 2 * p * r / (p + r) if p + r else 0
    return p, r, f

print("=" * 72)
print("  RE BASELINE REPORT (wf_cid_re_llm_linear, 500 articles)")
print("=" * 72)

print(f"""
OVERALL METRICS
  Micro:  P={mip:.3f}  R={mir:.3f}  F1={mif:.3f}
  Macro:  P={sum(row['tp']/(row['tp']+row['fp']) if row['tp']+row['fp'] else 0 for row in rows)/500:.3f}  R={sum(row['tp']/(row['tp']+row['fn']) if row['tp']+row['fn'] else 0 for row in rows)/500:.3f}
  Total:  TP={mtp}  FP={mfp}  FN={mfn}  Pairs={sum(r['n_pairs'] for r in rows)}
""")

print("TOP 20 WORST ARTICLES (by FP+FN impact)")
print("-" * 72)
print(f"{'#':>4} | {'TP':>3} {'FP':>3} {'FN':>3} | {'Imp':>4} | {'P':>5} {'R':>5} {'F1':>5} | 'Pairs' | 'Pred' | Text")
print("-" * 72)
for r in sorted(rows, key=lambda x: x['error_impact'], reverse=True)[:20]:
    p, rr, f = prf(r['tp'], r['fp'], r['fn'])
    print(f"{r['idx']:>4} | {r['tp']:>3} {r['fp']:>3} {r['fn']:>3} | {r['error_impact']:>4} | {p:.3f} {rr:.3f} {f:.3f} | {r['n_pairs']:>5} | {r['n_predicted']:>5} | {r['text_preview'][:55]}")

print()

# F1 projection scenarios
print("F1 PROJECTION SCENARIOS")
print("-" * 72)
scenarios = [
    ("Current baseline", 0, 0),
    ("Optimistic: -30% FP, -20% FN", 0.30, 0.20),
    ("Ambitious: -50% FP, -30% FN", 0.50, 0.30),
    ("Aggressive: -60% FP, -40% FN", 0.60, 0.40),
    ("Very aggressive: -70% FP, -50% FN", 0.70, 0.50),
    ("Target F1=0.80 needed: -80% FP, -60% FN", 0.80, 0.60),
    ("Oracle (gold pairs only): assume 40% fewer pairs", 0.20, 0.50),
]
for label, fp_cut, fn_improve in scenarios:
    new_fp = int(mfp * (1 - fp_cut))
    new_fn = int(mfn * (1 - fn_improve))
    p, r, f = prf(mtp, new_fp, new_fn)
    print(f"  {label:40s} → P={p:.3f}  R={r:.3f}  F1={f:.3f}")

print()
print("OPTIMIZED GRAPH ANALYSIS")
print("-" * 72)
print("""
Optimized graph (wf_cid_re_llm_linear_opt_20260529_143039_r2):
- Same nodes, edges, subgraph as baseline
- Pins agentVersions: relation_verify_llm → v0007
- Current agent definition ALREADY matches v0007 prompt content
- Primary delta: version pinning ensures reproducibility

v0007 change_note: "LLM over-rejects causal relations using overly strict patterns.
Expands accepted causal language to include 'associated with', 'risk factor', 'may
cause', 'can lead to', 'due to', 'implicated in', 'side effect', 'adverse effect',
This was the LAST optimization iteration (from dev tuning on 20 articles).
""")

print("F1=0.80 FEASIBILITY ASSESSMENT")
print("-" * 72)
print("""
REQUIRED:  P≈0.75 AND R≈0.86  (or equivalent combos)
  - P=0.75 requires cutting FP from 1,010 → ~250  (-75%)
  - R=0.86 requires cutting FN from 314 → ~120  (-62%)

CURRENT BOTTLENECKS:
  1. Hypernym filter generates 9.6 pairs/article on average (4,785 total)
  2. LLM verifier says "$" for 36.9% of pairs (1,767 predicted, only 752 correct)
  3. Most errors are FP (1,010) — the LLM is too permissive about causation
  4. The optimized v0007 actually EXPANDED accepted causal language
     → likely INCREASES FP (not reduces) while decreasing FN

VERDICT: F1=0.80 is NOT achievable with v0007-level prompt changes alone.

  - Realistic ceiling with optimized prompt: F1 ≈ 0.60-0.65
    (modest FP reduction from stricter rejection of co-occurrence)
  - Fundamental bottleneck: hypernym filter generates too many candidate pairs
  - To reach F1=0.80, you need a DIFFERENT approach:
    a) Better pair generation (semantic filtering, not just hypernyms)
    b) Hybrid NER+RE (use entity linking confidence)
    c) Prompt that distinguishes causal vs associative more sharply
    d) Post-processing: require stronger evidence for common associations

Running the optimized graph is still worthwhile to get the actual number.
""")
