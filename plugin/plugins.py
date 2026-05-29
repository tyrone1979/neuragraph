from typing import List, Dict, Any
import os
import numpy as np
import json
from urllib import parse, request

class Plugin:

    def load(self):
        pass
    async def aload(self):
        pass


# FlairTagger + full PGM with flair: sandbox/plugins_impl.py
# Main process keeps lightweight exec_globals for metrics-only PGM agents.


class PGMExecutorLite(Plugin):
    """In-process PGM (no flair). Used for eval_metrics and similar agents."""

    def load(self):
        safe_builtins = {
            "range": range,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "enumerate": enumerate,
            "zip": zip,
            "max": max,
            "min": min,
            "sum": sum,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "isinstance": isinstance,
        }

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            raise ImportError(
                f"Import {name} not allowed in main-process PGM; use plugin sandbox for flair."
            )

        safe_builtins["__import__"] = safe_import
        return {
            "exec_globals": {
                "__builtins__": safe_builtins,
                "__result__": None,
            }
        }


class PGMExecutorInProcess(Plugin):
    """Full in-process PGM when PLUGIN_SANDBOX=0 (includes flair via safe_import)."""

    def load(self):
        safe_builtins = {
            "range": range,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "enumerate": enumerate,
            "zip": zip,
            "max": max,
            "min": min,
            "sum": sum,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "isinstance": isinstance,
        }

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            allowed = {"flair", "flair.data"}
            if name not in allowed:
                raise ImportError(f"Import {name} not allowed")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins["__import__"] = safe_import
        try:
            import pathlib
            from flair.models import SequenceTagger

            model_dir = (
                pathlib.Path(__file__).resolve().parent.parent
                / "models"
                / "hunflair2-ner"
                / "pytorch_model.bin"
            )
            tag = None
            if model_dir.exists():
                tag = SequenceTagger.load(str(model_dir))
        except ImportError:
            tag = None
        out = {
            "exec_globals": {
                "__builtins__": safe_builtins,
                "__result__": None,
            }
        }
        if tag is not None:
            out["tag"] = tag
        return out


# PGMExecutorInProcess used only when PLUGIN_SANDBOX=0 (see plugin_loader skip rules)




'''
DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"

class PostgresCheckpointer(Plugin):

    def load(self):
        from langgraph.checkpoint.postgres import PostgresSaver
        sync_cm = PostgresSaver.from_conn_string(DB_URI)
        sync_saver = sync_cm.__enter__()
        sync_saver.setup()

        output={
            "postgres_sync_cm" : sync_cm,
            "PostgresSaver": sync_saver,
        }
        return output

    async def aload(self):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async_cm = AsyncPostgresSaver.from_conn_string(DB_URI)
        async_saver = await async_cm.__aenter__()
        output = {
            "postgres_async_cm": async_cm,
            "AsyncPostgresSaver": async_saver
        }
        return output
'''

class MemoryCheckpointer(Plugin):
    def load(self):
        from langgraph.checkpoint.memory import InMemorySaver
        memory = InMemorySaver()
        return {"InMemorySaver": memory}


class MeshOntology(Plugin):
    """Fetch MeSH synonym/hypernym facts from NLM public endpoints."""

    def load(self):
        class MeSHLookup:
            BASE = "https://id.nlm.nih.gov/mesh"

            @staticmethod
            def _http_get_json(url: str, params: dict | None = None) -> Any:
                query = parse.urlencode(params or {})
                full_url = f"{url}?{query}" if query else url
                req = request.Request(
                    full_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "agentic-llmre/mesh-lookup",
                    },
                )
                with request.urlopen(req, timeout=12) as resp:
                    raw = resp.read().decode("utf-8")
                return json.loads(raw)

            @staticmethod
            def _to_mesh_id(resource: str) -> str:
                return resource.rstrip("/").split("/")[-1]

            @staticmethod
            def lookup_descriptors(label: str, *, limit: int = 3, match: str = "contains") -> list[dict]:
                """Lookup descriptor candidates by label via MeSH lookup API."""
                rows = MeSHLookup._http_get_json(
                    f"{MeSHLookup.BASE}/lookup/descriptor",
                    {"label": label, "match": match, "limit": max(1, int(limit))},
                )
                out = []
                for row in rows or []:
                    resource = row.get("resource") or ""
                    out.append(
                        {
                            "mesh_id": MeSHLookup._to_mesh_id(resource) if resource else "",
                            "label": row.get("label") or "",
                            "resource": resource,
                        }
                    )
                return [r for r in out if r.get("mesh_id")]

            @staticmethod
            def _sparql(query: str) -> list[dict]:
                payload = MeSHLookup._http_get_json(
                    f"{MeSHLookup.BASE}/sparql",
                    {
                        "query": query,
                        "format": "JSON",
                    },
                )
                return (((payload or {}).get("results") or {}).get("bindings") or [])

            @staticmethod
            def get_synonyms(mesh_id: str) -> list[str]:
                q = f"""
PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
SELECT DISTINCT ?syn
WHERE {{
  <http://id.nlm.nih.gov/mesh/{mesh_id}> meshv:preferredConcept ?c .
  ?c meshv:term ?t .
  {{
    ?t meshv:prefLabel ?syn .
  }} UNION {{
    ?t meshv:altLabel ?syn .
  }}
}}
"""
                rows = MeSHLookup._sparql(q)
                vals = [((r.get("syn") or {}).get("value") or "").strip() for r in rows]
                return sorted({v for v in vals if v})

            @staticmethod
            def get_hypernyms(mesh_id: str) -> list[dict]:
                q = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
SELECT DISTINCT ?broader ?broaderLabel
WHERE {{
  <http://id.nlm.nih.gov/mesh/{mesh_id}> meshv:broaderDescriptor ?broader .
  ?broader rdfs:label ?broaderLabel .
}}
"""
                rows = MeSHLookup._sparql(q)
                out = []
                for row in rows:
                    resource = ((row.get("broader") or {}).get("value") or "").strip()
                    label = ((row.get("broaderLabel") or {}).get("value") or "").strip()
                    if not resource:
                        continue
                    out.append(
                        {
                            "mesh_id": MeSHLookup._to_mesh_id(resource),
                            "label": label,
                            "resource": resource,
                        }
                    )
                uniq = {(x["mesh_id"], x["label"], x["resource"]): x for x in out}
                return sorted(uniq.values(), key=lambda x: (x["label"], x["mesh_id"]))

        return {"MeSHLookup": MeSHLookup}


class CidDatasetPlugin(Plugin):
    """Build/extract CID tuning and test CSV datasets from PubTator gold sources."""

    def load(self):
        class CidDatasetBuilder:
            @staticmethod
            def build_full(*args, **kwargs):
                from service.dataset_cid import build_structured_full
                return build_structured_full(*args, **kwargs)

            @staticmethod
            def build_tuning(*args, **kwargs):
                from service.dataset_cid import build_tuning_dataset
                return build_tuning_dataset(*args, **kwargs)

            @staticmethod
            def extract_test(*args, **kwargs):
                from service.dataset_cid import extract_test_dataset
                return extract_test_dataset(*args, **kwargs)

            @staticmethod
            def registry(*args, **kwargs):
                from service.dataset_cid import get_registry_status
                return get_registry_status(*args, **kwargs)

        return {"CidDatasetBuilder": CidDatasetBuilder}


class Metrics(Plugin):

    def load(self):
        class MetricsCalculation:

            @staticmethod
            def parse_relation_pairs(raw):
                """Parse CID/RE pipe lines 'head | rel | tail' into [(head, tail), ...]."""
                if raw is None or raw == "":
                    return []
                lines = []
                if isinstance(raw, str):
                    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                elif isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, str):
                            lines.extend(
                                ln.strip()
                                for ln in item.splitlines()
                                if ln.strip()
                            )
                        else:
                            lines.append(item)
                else:
                    return []

                pairs = []
                for item in lines:
                    if isinstance(item, dict):
                        h = (
                            item.get("head_entity")
                            or item.get("chemical")
                            or item.get("head")
                            or ""
                        ).lower().strip()
                        t = (
                            item.get("tail_entity")
                            or item.get("disease")
                            or item.get("tail")
                            or ""
                        ).lower().strip()
                        if h and t:
                            pairs.append((h, t))
                    elif isinstance(item, str) and "|" in item:
                        parts = [p.strip() for p in item.split("|")]
                        if len(parts) >= 3:
                            h, t = parts[0].lower(), parts[-1].lower()
                        elif len(parts) == 2:
                            h, t = parts[0].lower(), parts[1].lower()
                        else:
                            continue
                        if h in ("chemical", "head") or t in ("disease", "tail"):
                            continue
                        if h and t:
                            pairs.append((h, t))
                    elif isinstance(item, (list, tuple)):
                        if len(item) >= 3:
                            pairs.append((str(item[0]).lower(), str(item[2]).lower()))
                        elif len(item) == 2:
                            pairs.append((str(item[0]).lower(), str(item[1]).lower()))
                return pairs

            @staticmethod
            def calculate(expected, predicted):
                from ast import literal_eval
                from sklearn.metrics import precision_recall_fscore_support

                # --------------- 统一字符串 → Python 对象 ---------------
                if isinstance(expected, str):
                    if "|" in expected:
                        expected = MetricsCalculation.parse_relation_pairs(expected)
                    else:
                        expected = literal_eval(expected)
                if isinstance(predicted, str):
                    if "|" in predicted:
                        predicted = MetricsCalculation.parse_relation_pairs(predicted)
                    else:
                        predicted = literal_eval(predicted)

                def flatten_to_binary(gold_set, pred_set):
                    """将两个集合转换为二进制标签列表"""
                    y_true, y_pred = [], []
                    for item in gold_set | pred_set:
                        y_true.append(int(item in gold_set))
                        y_pred.append(int(item in pred_set))
                    return y_true, y_pred

                # --------------- 辅助函数：去重 + 小写归一化 ---------------
                def norm_doc(doc):
                    return {k: list(dict.fromkeys(ent.lower() for ent in v))
                            for k, v in doc.items()}

                # --------------- 格式1: list of tuples [(),()] 或 [[],[]] ---------------
                if isinstance(expected, list) and isinstance(predicted, list):
                    def normalize_list_of_pairs(lst):
                        result = []
                        for item in lst:
                            if len(item) == 3:
                                result.append((str(item[0]).lower(), str(item[2]).lower()))
                            elif len(item) == 2:
                                entity, label = item
                                result.append((entity.lower(), label.lower()))
                        return result

                    expected_pairs = normalize_list_of_pairs(expected)
                    predicted_pairs = normalize_list_of_pairs(predicted)

                    gold_set = set(expected_pairs)
                    pred_set = set(predicted_pairs)

                    # 计算 TP/FP/FN（集合运算）
                    tp = len(gold_set & pred_set)
                    fp = len(pred_set - gold_set)
                    fn = len(gold_set - pred_set)

                    # 原指标计算逻辑保留
                    y_true, y_pred = flatten_to_binary(gold_set, pred_set)
                    prec, rec, f1, _ = precision_recall_fscore_support(
                        y_true, y_pred, average='binary', zero_division=0)

                    return {
                        "precision": float(prec),
                        "recall": float(rec),
                        "f1": float(f1),
                        "tp": tp,  # 新增
                        "fp": fp,  # 新增
                        "fn": fn  # 新增
                    }

                else:
                    # --------------- 老格式：{label:[ent,...]} ---------------
                    expected = norm_doc(expected)
                    predicted = norm_doc(predicted)

                    total_tp = total_fp = total_fn = 0
                    y_true, y_pred = [], []

                    for lbl in set(expected) | set(predicted):
                        g_set = set(expected.get(lbl, []))
                        p_set = set(predicted.get(lbl, []))

                        # 累加各 label 的 TP/FP/FN
                        total_tp += len(g_set & p_set)
                        total_fp += len(p_set - g_set)
                        total_fn += len(g_set - p_set)

                        y_t, y_p = flatten_to_binary(g_set, p_set)
                        y_true.extend(y_t)
                        y_pred.extend(y_p)

                    prec, rec, f1, _ = precision_recall_fscore_support(
                        y_true, y_pred, average='binary', zero_division=0)

                    return {
                        "precision": float(prec),
                        "recall": float(rec),
                        "f1": float(f1),
                        "tp": total_tp,  # 新增
                        "fp": total_fp,  # 新增
                        "fn": total_fn  # 新增
                    }

            def compute_micro_macro(metrics: Dict[Any, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
                """
                metrics: {idx: {'precision': float, 'recall': float, 'f1': float}, ...}
                返回 {'micro': {...}, 'macro': {...}}
                """
                if not metrics:
                    return {'micro': {'precision': 0., 'recall': 0., 'f1': 0.},
                            'macro': {'precision': 0., 'recall': 0., 'f1': 0.}}

                # 取出 value 列表，后续和原逻辑完全一致
                metrics_list = list(metrics.values())

                # ---------- macro：直接平均 ----------
                macro = {
                    'precision': float(np.mean([m['precision'] for m in metrics_list if 'precision' in m ])),
                    'recall': float(np.mean([m['recall'] for m in metrics_list  if 'recall' in m ])),
                    'f1': float(np.mean([m['f1'] for m in metrics_list  if 'f1' in m]))
                }

                # ---------- micro：累 TP/FP/FN ----------
                tp_sum = sum(m['tp'] for m in metrics_list  if 'tp' in m)
                fp_sum = sum(m['fp'] for m in metrics_list  if 'fp' in m)
                fn_sum = sum(m['fn'] for m in metrics_list  if 'tp' in m)

                prec_micro = tp_sum / (tp_sum + fp_sum + 1e-15)
                rec_micro = tp_sum / (tp_sum + fn_sum + 1e-15)
                f1_micro = 2 * prec_micro * rec_micro / (prec_micro + rec_micro + 1e-15)

                return {'micro': {'precision': prec_micro, 'recall': rec_micro, 'f1': f1_micro},
                        'macro': macro}



        return {"MetricsCalculation": MetricsCalculation}
