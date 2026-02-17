import json
from typing import List, Dict, Any, Tuple

from flask import Flask, request, jsonify
from flask_cors import CORS  # 解决跨域问题

# ===================== 初始化配置 =====================
app = Flask(__name__)
CORS(app)  # 允许Dify跨域调用


# ===================== 核心工具函数（复用你的逻辑） =====================
def convert_to_str(text):
    """清洗LLM返回结果"""
    text = text.replace(" ", "")
    return text.replace("'", "")


def create_entity_pair(expected_entities: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """生成Chemical-Disease实体对"""
    heads = []
    tails = []
    if 'Chemical' in expected_entities:
        heads = expected_entities['Chemical']
    if 'Disease' in expected_entities:
        tails = expected_entities['Disease']
    pairs = []
    for head in heads:
        for tail in tails:
            pairs.append({"head": head, "tail": tail})
    return pairs


def entity_link(result: str, pair: Dict[str, str], entity_link: Dict[str, str]) -> Tuple[str, str] | tuple:
    """实体链接映射（LLM返回$时映射，否则返回空元组）"""
    if result == '$':
        return (entity_link[pair['head']], entity_link[pair["tail"]])
    return ()


# ===================== RE指标计算类（适配RE任务） =====================
class MetricsCalculation:
    """RE任务指标计算：Precision/Recall/F1（微平均/宏平均）"""

    @staticmethod
    def _calculate_single_metric(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
        """计算Precision/Recall/F1（处理分母为0）"""
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return round(precision, 4), round(recall, 4), round(f1, 4)

    @staticmethod
    def calculate_re_metrics(expected_relations: List[List[Tuple[str, str]]],
                             predicted_relations: List[List[Tuple[str, str]]]) -> Dict[str, Any]:
        """
        计算RE任务指标
        :param expected_relations: 真实关系列表 [[(head1,tail1), (head2,tail2)], ...]
        :param predicted_relations: 预测关系列表 [[(head1,tail1), (head2,tail2)], ...]
        :return: 指标字典
        """
        # 1. 初始化统计变量
        total_tp = 0  # 总真正例
        total_fp = 0  # 总假正例
        total_fn = 0  # 总假负例

        # 2. 遍历每个样本计算
        for exp_rel, pred_rel in zip(expected_relations, predicted_relations):
            exp_set = set(exp_rel)
            pred_set = set(pred_rel)

            # 统计单个样本的TP/FP/FN
            tp = len(exp_set & pred_set)  # 交集为TP
            fp = len(pred_set - exp_set)  # 预测有、真实无 → FP
            fn = len(exp_set - pred_set)  # 真实有、预测无 → FN

            # 累加全局统计量
            total_tp += tp
            total_fp += fp
            total_fn += fn

        # 3. 计算微平均指标（RE任务核心指标）
        micro_p, micro_r, micro_f1 = MetricsCalculation._calculate_single_metric(total_tp, total_fp, total_fn)

        return {
            "micro_average": {
                "precision": micro_p,
                "recall": micro_r,
                "f1": micro_f1
            },
            "global_statistics": {
                "total_tp": total_tp,
                "total_fp": total_fp,
                "total_fn": total_fn,
                "total_samples": len(expected_relations)
            }
        }


# ===================== Dify可调用的API接口 =====================
@app.route("/api/tools/create_entity_pair", methods=["POST"])
def create_entity_pair_api():
    """
    Dify调用：生成Chemical-Disease实体对
    请求格式：{"expected_entities": {"Chemical":["Dabrafenib"], "Disease":["melanoma"]}}
    """
    try:
        data = request.get_json()
        if not data or "expected_entities" not in data:
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "缺失参数：expected_entities"
            }), 400

        expected_entities = data["expected_entities"]
        pairs = create_entity_pair(expected_entities)

        return jsonify({
            "status": "success",
            "data": {"entity_pairs": pairs},
            "message": "实体对生成成功"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": {},
            "message": f"实体对生成失败：{str(e)}"
        }), 500


@app.route("/api/tools/entity_link", methods=["POST"])
def entity_link_api():
    """
    Dify调用：实体链接映射
    请求格式：
    {
        "result": "$",
        "pair": {"head": "Dabrafenib", "tail": "melanoma"},
        "entity_link": {"Dabrafenib": "C0001", "melanoma": "D0001"}
    }
    """
    try:
        data = request.get_json()
        # 参数校验
        required_fields = ["result", "pair", "entity_link"]
        if not data or not all(f in data for f in required_fields):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": f"缺失参数：{', '.join(required_fields)}"
            }), 400

        # 执行实体链接
        result = data["result"]
        pair = data["pair"]
        entity_link_map = data["entity_link"]
        link_result = entity_link(result, pair, entity_link_map)

        return jsonify({
            "status": "success",
            "data": {"linked_pair": link_result},
            "message": "实体链接成功"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": {},
            "message": f"实体链接失败：{str(e)}"
        }), 500


@app.route("/api/tools/calculate_re_metrics", methods=["POST"])
def calculate_re_metrics_api():
    """
    Dify调用：RE任务指标计算
    请求格式：
    {
        "expected_relations": [[("C0001", "D0001")], []],
        "predicted_relations": [[("C0001", "D0001")], []]
    }
    """
    try:
        data = request.get_json()
        # 参数校验
        required_fields = ["expected_relations", "predicted_relations"]
        if not data or not all(f in data for f in required_fields):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": f"缺失参数：{', '.join(required_fields)}"
            }), 400

        # 类型校验
        expected = data["expected_relations"]
        predicted = data["predicted_relations"]
        if not isinstance(expected, list) or not isinstance(predicted, list):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "expected_relations和predicted_relations必须是列表"
            }), 400
        if len(expected) != len(predicted):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": f"真实关系数量({len(expected)})与预测数量({len(predicted)})不匹配"
            }), 400

        # 计算指标
        metrics = MetricsCalculation.calculate_re_metrics(expected, predicted)

        return jsonify({
            "status": "success",
            "data": metrics,
            "message": "RE指标计算成功"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": {},
            "message": f"RE指标计算失败：{str(e)}"
        }), 500


# ===================== 测试入口 =====================
if __name__ == "__main__":
    # 启动服务，端口5001（避免和NER Tool端口冲突）
    app.run(host="0.0.0.0", port=5001, debug=True)