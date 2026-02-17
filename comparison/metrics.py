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



