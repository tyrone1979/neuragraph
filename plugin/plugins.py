from typing import List, Dict, Any
import numpy as np

class Plugin:

    def load(self):
        pass
    async def aload(self):
        pass

class FlairTagger(Plugin):
    def load(self):
        from flair.models import SequenceTagger
        import pathlib
        MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models" / "hunflair2-ner" / "pytorch_model.bin"
        flair_tagger = SequenceTagger.load(str(MODEL_DIR))
        return {"tag": flair_tagger}

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


class Metrics(Plugin):

    def load(self):
        class MetricsCalculation:

            @staticmethod
            def calculate(expected, predicted):
                from ast import literal_eval
                import numpy as np
                from sklearn.metrics import precision_recall_fscore_support

                # --------------- 统一字符串 → dict ---------------
                if isinstance(expected, str):
                    expected = literal_eval(expected)
                if isinstance(predicted, str):
                    predicted = literal_eval(predicted)

                # --------------- 去重 + 小写归一化 ---------------
                def norm_doc(doc):
                    return {k: list(dict.fromkeys(ent.lower() for ent in v))
                            for k, v in doc.items()}

                # --------------- 格式分支 ---------------
                # 新格式：{"doc_id": {label:[ent,...]}}
                if all(isinstance(v, dict) for v in expected.values()):
                    docs_gold = {k: norm_doc(v) for k, v in expected.items()}
                    docs_pred = {k: norm_doc(v) for k, v in predicted.items()}

                    # ---- micro：实体级拉平 ----
                    y_true_micro, y_pred_micro = [], []
                    for doc_id in docs_gold.keys() | docs_pred.keys():
                        g_doc = docs_gold.get(doc_id, {})
                        p_doc = docs_pred.get(doc_id, {})
                        for lbl in set(g_doc) | set(p_doc):
                            g_set, p_set = set(g_doc.get(lbl, [])), set(p_doc.get(lbl, []))
                            for ent in g_set | p_set:
                                y_true_micro.append(int(ent in g_set))
                                y_pred_micro.append(int(ent in p_set))
                    prec_micro, rec_micro, f1_micro, _ = precision_recall_fscore_support(
                        y_true_micro, y_pred_micro, average='binary', zero_division=0)

                    # ---- macro：文档级平均 ----
                    doc_scores = []
                    for doc_id in docs_gold.keys() | docs_pred.keys():
                        g_doc = docs_gold.get(doc_id, {})
                        p_doc = docs_pred.get(doc_id, {})
                        y_true, y_pred = [], []
                        for lbl in set(g_doc) | set(p_doc):
                            g_set, p_set = set(g_doc.get(lbl, [])), set(p_doc.get(lbl, []))
                            for ent in g_set | p_set:
                                y_true.append(int(ent in g_set))
                                y_pred.append(int(ent in p_set))
                        prec, rec, f1, _ = precision_recall_fscore_support(
                            y_true, y_pred, average='binary', zero_division=0)
                        doc_scores.append([prec, rec, f1])
                    prec_macro, rec_macro, f1_macro = np.mean(doc_scores, axis=0)

                    return {"micro": {"precision": prec_micro, "recall": rec_micro, "f1": f1_micro},
                            "macro": {"precision": prec_macro, "recall": rec_macro, "f1": f1_macro}}

                # --------------- 老格式：{label:[ent,...]} ---------------
                expected = norm_doc(expected)
                predicted = norm_doc(predicted)

                y_true, y_pred = [], []
                for lbl in set(expected) | set(predicted):
                    g_set, p_set = set(expected.get(lbl, [])), set(predicted.get(lbl, []))
                    for ent in g_set | p_set:
                        y_true.append(int(ent in g_set))
                        y_pred.append(int(ent in p_set))
                prec, rec, f1, _ = precision_recall_fscore_support(
                    y_true, y_pred, average='binary', zero_division=0)
                return {"precision": prec, "recall": rec, "f1": f1}

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
                macro = {k: float(np.mean([m[k] for m in metrics_list])) for k in ('precision', 'recall', 'f1')}

                # ---------- micro：累 TP/FP/FN ----------
                tp_sum = fp_sum = fn_sum = 0.
                for m in metrics_list:
                    tp = m['precision']  # support=1
                    fp = 1 - tp
                    fn = 1 - m['recall']
                    tp_sum += tp
                    fp_sum += fp
                    fn_sum += fn

                prec_micro = tp_sum / (tp_sum + fp_sum + 1e-15)
                rec_micro = tp_sum / (tp_sum + fn_sum + 1e-15)
                f1_micro = 2 * prec_micro * rec_micro / (prec_micro + rec_micro + 1e-15)

                return {'micro': {'precision': prec_micro, 'recall': rec_micro, 'f1': f1_micro},
                        'macro': macro}



        return {"MetricsCalculation": MetricsCalculation}