#!/usr/bin/env python3
"""One-off: aggregate metrics from result/*/states.json for paper tables."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def prf(tp: int, fp: int, fn: int):
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return round(prec, 3), round(rec, 3), round(f1, 3)


def sample_metrics(s: dict) -> dict:
    m = s.get("metrics") or {}
    if not m and isinstance(s.get("state"), dict):
        m = s["state"].get("metrics") or {}
    return m


def aggregate_states(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    samples = []
    if isinstance(data, dict):
        for k, v in sorted(data.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
            if str(k).isdigit() and isinstance(v, dict):
                samples.append(v)
    if not samples and isinstance(data, list):
        samples = data

    micro_tp = micro_fp = micro_fn = 0
    macro_ps, macro_rs, macro_fs = [], [], []
    rel_micro = rel_macro = None

    for s in samples:
        m = sample_metrics(s)
        if not m:
            continue
        if "rel_micro" in m or "rel_macro" in m:
            rel_micro = m.get("rel_micro") or rel_micro
            rel_macro = m.get("rel_macro") or rel_macro
        if "micro" in m and isinstance(m["micro"], dict):
            rel_micro = m["micro"]
        if "macro" in m and isinstance(m["macro"], dict):
            rel_macro = m["macro"]

        tp = int(m.get("rel_tp") or m.get("tp") or 0)
        fp = int(m.get("rel_fp") or m.get("fp") or 0)
        fn = int(m.get("rel_fn") or m.get("fn") or 0)
        if tp + fp + fn:
            micro_tp += tp
            micro_fp += fp
            micro_fn += fn
        p, r, f = m.get("precision"), m.get("recall"), m.get("f1")
        if p is not None and r is not None and f is not None:
            macro_ps.append(float(p))
            macro_rs.append(float(r))
            macro_fs.append(float(f))

    out = {"n_samples": len(samples)}
    if micro_tp + micro_fp + micro_fn:
        out["micro"] = prf(micro_tp, micro_fp, micro_fn)
    if macro_fs:
        out["macro"] = (
            round(sum(macro_ps) / len(macro_ps), 3),
            round(sum(macro_rs) / len(macro_rs), 3),
            round(sum(macro_fs) / len(macro_fs), 3),
        )
    if rel_micro:
        out["rel_micro"] = (
            round(float(rel_micro.get("precision", 0)), 3),
            round(float(rel_micro.get("recall", 0)), 3),
            round(float(rel_micro.get("f1", 0)), 3),
        )
    if rel_macro:
        out["rel_macro"] = (
            round(float(rel_macro.get("precision", 0)), 3),
            round(float(rel_macro.get("recall", 0)), 3),
            round(float(rel_macro.get("f1", 0)), 3),
        )
    if samples:
        out["metric_keys"] = sorted(set(sample_metrics(samples[0]).keys()))
    return out


def main():
    result_dir = ROOT / "result"
    print("=== Experiments with states.json ===\n")
    for exp_dir in sorted(result_dir.iterdir()):
        if not exp_dir.is_dir():
            continue
        sf = exp_dir / "states.json"
        if not sf.is_file():
            continue
        if sf.stat().st_size > 2_000_000:
            print(f"{exp_dir.name}: SKIP huge ({sf.stat().st_size} bytes)")
            continue
        meta_path = ROOT / "meta" / "exps" / f"{exp_dir.name}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        agg = aggregate_states(sf)
        print(
            f"{exp_dir.name}\n"
            f"  runner={meta.get('runner_id', '?')}\n"
            f"  test={meta.get('test_dataset') or meta.get('dataset', '?')}\n"
            f"  n_cfg={meta.get('samples')} status={meta.get('status')}\n"
            f"  agg={json.dumps(agg, ensure_ascii=False)}\n"
        )

    for fname in sorted(result_dir.glob("opt_compare_*.json")):
        print(f"=== {fname.name} ===\n")
        print(json.dumps(json.loads(fname.read_text(encoding="utf-8")), indent=2)[:8000])
        print()


if __name__ == "__main__":
    main()
