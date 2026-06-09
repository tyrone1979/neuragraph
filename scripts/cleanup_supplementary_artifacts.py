"""Backup meta/result and keep only SUPPLEMENTARY.md-related experiments and agent versions."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / "_backup"

# Table S15 / S15B / S16 / S16b / S17 / S18 + §3.3 opt_compare lineage
KEEP_EXP_IDS = {
    "064f47ac-2d08-4e9a-85e3-2ca2e564c7da",
    "aba808f2-46ad-4585-984f-633955729315",
    "678a855f-1f8a-492e-9d39-be37df122795",
    "f860e6d3-51fd-4b24-aa51-3d0fb9c88907",
    "bffea244-c3dd-4b97-98f2-9ed4d7bb895a",
    "opt_base_tune_81781d50",
    "opt_cand_ddi_c2_8cb2b66e",
    "f859b257-12fa-4c9e-951f-cc8088d9461d",
    "309d1c78-acd6-499b-b97f-ed5bcba3ca57",
    "a728966d-baea-460b-ab8d-5be74ed4ff31",
    "576ead7a-0027-48e4-b2ea-7170a080f157",
    "031fff5a-a91b-48f0-b9cd-9aac3540ce0c",
    "68ff0297-e2fe-4c57-84ca-d5b7b390a4c1",
    # §3.3 wizard (opt_compare_20260529_143039.json)
    "df068614-cb88-416c-813f-2803bc81331d",
    "opt_base_tune_0309e9f6",
    "opt_best_20260529_143039_4aba4c72",
    "opt_cand_20260529_143039_r1_c50f923a",
    "opt_pinned_20260529_143039_r1_6356ef2b",
    "opt_cand_20260529_143039_r2_a1e0d132",
    "opt_pinned_20260529_143039_r2_61e7097f",
}

KEEP_RESULT_FILES = {
    "opt_compare_20260529_143039.json",
}

KEEP_AGENT_VERSIONS: dict[str, set[str]] = {
    "relation_verify_llm": {"v0007", "v0008", "v0010", "v0013"},
    "relation_result_to_id_pair": {"v0001", "v0003"},
}

GRAPHS_TO_RESTORE = [
    "wf_cid_re_llm_linear_opt_20260604.json",
    "wf_cid_re_llm_linear_opt_20260529_143039.json",
    "wf_cid_re_llm_linear_opt_20260529_143039_r1.json",
    "wf_cid_re_llm_linear_opt_20260529_143039_r2.json",
]


def _backup_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        raise RuntimeError(f"Backup destination already exists: {dst}")
    print(f"Backing up {src} -> {dst}")
    shutil.copytree(src, dst)


def _exp_id_from_meta(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return path.stem
    return str(data.get("exp_id") or data.get("id") or path.stem).strip()


def _trim_agent_versions(agent_id: str, keep: set[str]) -> list[str]:
    agent_dir = ROOT / "meta" / "agent_versions" / agent_id
    index_path = agent_dir / "index.json"
    if not index_path.is_file():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    removed: list[str] = []
    kept_entries = []
    for item in index.get("versions") or []:
        ver = str(item.get("version") or "")
        if ver in keep:
            kept_entries.append(item)
        else:
            removed.append(ver)
            ver_path = agent_dir / f"{ver}.json"
            if ver_path.is_file():
                ver_path.unlink()
    latest = ""
    if kept_entries:
        kept_entries.sort(key=lambda x: x.get("created_at", ""))
        latest = str(kept_entries[-1].get("version") or "")
    index["versions"] = kept_entries
    index["latest"] = latest
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return removed


def _restore_graphs() -> None:
    archived = ROOT / "meta" / "graphs" / "_archived"
    graphs = ROOT / "meta" / "graphs"
    for name in GRAPHS_TO_RESTORE:
        src = archived / name
        dst = graphs / name
        if src.is_file() and not dst.is_file():
            print(f"Restoring graph {name}")
            shutil.copy2(src, dst)


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"{stamp}_meta_result"
    backup_dir.mkdir(parents=True, exist_ok=True)
    _backup_tree(ROOT / "meta", backup_dir / "meta")
    _backup_tree(ROOT / "result", backup_dir / "result")

    _restore_graphs()

    exps_dir = ROOT / "meta" / "exps"
    deleted_exps: list[str] = []
    for path in sorted(exps_dir.glob("*.json")):
        eid = _exp_id_from_meta(path)
        if eid not in KEEP_EXP_IDS:
            path.unlink()
            deleted_exps.append(eid)

    result_dir = ROOT / "result"
    deleted_results: list[str] = []
    for path in sorted(result_dir.iterdir()):
        name = path.name
        if path.is_dir():
            if name not in KEEP_EXP_IDS:
                shutil.rmtree(path)
                deleted_results.append(name)
        elif path.is_file() and name not in KEEP_RESULT_FILES:
            path.unlink()
            deleted_results.append(name)

    removed_versions: dict[str, list[str]] = {}
    for agent_id, keep in KEEP_AGENT_VERSIONS.items():
        removed_versions[agent_id] = _trim_agent_versions(agent_id, keep)

    summary = {
        "backup_dir": str(backup_dir),
        "kept_exp_count": len(KEEP_EXP_IDS),
        "deleted_exps": deleted_exps,
        "deleted_result_entries": deleted_results,
        "removed_agent_versions": removed_versions,
        "kept_agent_versions": {k: sorted(v) for k, v in KEEP_AGENT_VERSIONS.items()},
    }
    summary_path = backup_dir / "cleanup_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
