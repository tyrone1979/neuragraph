from typing import List, Dict, Any
import numpy as np

class Plugin:

    def load(self):
        pass
    async def aload(self):
        pass

class FlairTagger(Plugin):
    def load(self):
        from flair.nn import Classifier
        '''
        #if you want to load local model file.
        from flair.models import SequenceTagger
        import pathlib
        MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models" / "hunflair2-ner" / "pytorch_model.bin"
        flair_tagger = SequenceTagger.load(str(MODEL_DIR)) 
        '''
        flair_tagger = Classifier.load("hunflair2")
        return {"tag": flair_tagger}

class PGMExecutor(Plugin):
    def load(self):
        safe_builtins = {
                    'range': range, 'len': len, 'str': str, 'int': int,
                    'float': float, 'bool': bool, 'list': list, 'dict': dict,
                    'set': set, 'tuple': tuple, 'enumerate': enumerate,
                    'zip': zip, 'max': max, 'min': min, 'sum': sum,
                    'abs': abs, 'round': round, 'sorted': sorted,
                    'isinstance': isinstance
        }

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
                allowed = {
                        'flair',
                        'flair.data'
                }
                if name not in allowed:
                        raise ImportError(f"Import {name} not allowed")
                return __import__(name, globals, locals, fromlist, level)

        safe_builtins['__import__'] = safe_import
        exec_globals = {
            '__builtins__': safe_builtins,
            '__result__': None
        }

        return {"exec_globals": exec_globals}




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
                from sklearn.metrics import precision_recall_fscore_support

                # --------------- 统一字符串 → Python 对象 ---------------
                if isinstance(expected, str):
                    expected = literal_eval(expected)
                if isinstance(predicted, str):
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
                            if len(item) == 2:
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
