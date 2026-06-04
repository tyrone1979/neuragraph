"""Analyze RE baseline: top-20 worst articles, FP/FN breakdown, optimized F1 prediction."""
import json
from collections import Counter

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
    text = (s[str(k)].get('text', '') or '')[:300]
    error_impact = fp + fn
    p = float(m.get('precision', 0))
    r = float(m.get('recall', 0))
    f = float(m.get('f1', 0))
    rows.append({
        'idx': k, 'tp': tp, 'fp': fp, 'fn': fn,
        'p': p, 'r': r, 'f': f,
        'error_impact': error_impact,
        'n_pairs': len(pairs),
        'n_predicted': len(relations),
        'text_preview': text,
    })

# Aggregate
mtp = sum(r['tp'] for r in rows)
mfp = sum(r['fp'] for r in rows)
mfn = sum(r['fn'] for r in rows)
print("=" * 70)
print("RE BASELINE ANALYSIS (500 articles)")
print("=" * 70)
mip = mtp / (mtp + mfp) if mtp + mfp else 0
mir = mtp / (mtp + mfn) if mtp + mfn else 0
mif = 2 * mip * mir / (mip + mir) if mip + mir else 0
print(f"\nOverall Micro: P={mip:.3f}  R={mir:.3f}  F1={mif:.3f}")
print(f"Total: TP={mtp}  FP={mfp}  FN={mfn}")

# Top 20 by error_impact
by_impact = sorted(rows, key=lambda r: r['error_impact'], reverse=True)
by_fp = sorted(rows, key=lambda r: r['fp'], reverse=True)
by_fn = sorted(rows, key=lambda r: r['fn'], reverse=True)

print("\n" + "=" * 70)
print("TOP 20 BY ERROR IMPACT (FP+FN) — these hurt F1 the most")
print("=" * 70)
print(f"{'#':>4}  {'TP':>3} {'FP':>3} {'FN':>3} {'Impact':>6} {'P':>5} {'R':>5} {'F1':>5}  {'Pairs':>5} {'Pred':>5}  Text")
print("-" * 70)
for r in by_impact[:20]:
    print(f"{r['idx']:>4}  {r['tp']:>3} {r['fp']:>3} {r['fn']:>3} {r['error_impact']:>6} {r['p']:.3f} {r['r']:.3f} {r['f']:.3f}  {r['n_pairs']:>5} {r['n_predicted']:>5}  {r['text_preview'][:60]}")

# Check: how many pairs get verified vs predicted
total_pairs = sum(r['n_pairs'] for r in rows)
total_predicted = sum(r['n_predicted'] for r in rows)
print(f"\nTotal pairs generated (hypernym filter): {total_pairs}")
print(f"Total predicted relations (RE verified): {total_predicted}")
print(f"Verification rate: {total_predicted/total_pairs*100:.1f}%")
print(f"Avg pairs/article: {total_pairs/500:.1f}")
print(f"Avg predicted/article: {total_predicted/500:.1f}")

# How many errors come from over-prediction vs under-prediction
print("\n" + "=" * 70)
print("F1 projection: what if we cut FP by X% and improve FN by Y%")
print("=" * 70)
for fp_cut, fn_improve in [(0, 0), (0.2, 0.1), (0.3, 0.2), (0.4, 0.3), (0.5, 0.4), (0.6, 0.5)]:
    new_fp = int(mfp * (1 - fp_cut))
    new_fn = int(mfn * (1 - fn_improve))
    p = mtp / (mtp + new_fp) if mtp + new_fp else 0
    r = mtp / (mtp + new_fn) if mtp + new_fn else 0
    f = 2 * p * r / (p + r) if p + r else 0
    print(f"  Cut FP {fp_cut*100:.0f}%  Improve FN {fn_improve*100:.0f}%  →  P={p:.3f}  R={r:.3f}  F1={f:.3f}")

# What's the ceiling? If we fix ALL FN and remove ALL spurious FP
print(f"\nCeiling (fix all FN, keep all FP): P={mip:.3f}  R=1.000  F1={2*mip*1/(mip+1):.3f}")
print(f"Ceiling (fix all FP, keep all FN): P=1.000  R={mir:.3f}  F1={2*1*mir/(1+mir):.3f}")
print(f"Ceiling (fix half both): new_TP={mtp} new_FP={mfp//2} new_FN={mfn//2}")
half_p = mtp / (mtp + mfp//2) if mtp + mfp//2 else 0
half_r = mtp / (mtp + mfn//2) if mtp + mfn//2 else 0
half_f = 2 * half_p * half_r / (half_p + half_r) if half_p + half_r else 0
print(f"  → P={half_p:.3f}  R={half_r:.3f}  F1={half_f:.3f}")

# Error distribution
fp_dist = Counter()
fn_dist = Counter()
fp_articles = sorted([r for r in rows if r['fp'] > 0], key=lambda r: r['fp'], reverse=True)
fn_articles = sorted([r for r in rows if r['fn'] > 0], key=lambda r: r['fn'], reverse=True)

print("\n" + "=" * 70)
print("TOP 20 BY FP (over-prediction)")
print("=" * 70)
for r in fp_articles[:20]:
    print(f"  #{r['idx']:>3}: FP={r['fp']:>2}  P={r['p']:.3f}  R={r['r']:.3f}  F1={r['f']:.3f}  pairs={r['n_pairs']}  {r['text_preview'][:60]}")

print("\n" + "=" * 70)
print("TOP 20 BY FN (under-prediction)")
print("=" * 70)
for r in fn_articles[:20]:
    print(f"  #{r['idx']:>3}: FN={r['fn']:>2}  P={r['p']:.3f}  R={r['r']:.3f}  F1={r['f']:.3f}  pairs={r['n_pairs']}  {r['text_preview'][:60]}")
