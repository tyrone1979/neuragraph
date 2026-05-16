import json
import pathlib
from typing import List, Dict

from flask import Flask, request, jsonify
from flask_cors import CORS  # 解决Dify跨域调用问题，pip install flask-cors

# 导入NER核心依赖
from flair.models import SequenceTagger
from flair.data import Sentence


# ===================== 初始化配置 =====================
app = Flask(__name__)
CORS(app)  # 允许跨域请求（Dify调用必备）

# 1. 模型路径配置
MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models" / "hunflair2-ner" / "pytorch_model.bin"
# 2. 实体标签
LABELS = ["Chemical", "Disease"]
# 3. 初始化Flair模型（全局加载，避免重复初始化）
try:
    flair_tagger = SequenceTagger.load(str(MODEL_DIR))
except Exception as e:
    raise RuntimeError(f"加载Flair模型失败: {e}")

# ===================== 核心工具函数 =====================
def _convert_to_list(raw: str) -> List[str]:
    """处理Ollama返回的句子分割结果，转为列表"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 降级处理：按换行分割
        entities = [s.strip() for s in raw.split('\n') if s.strip()]
        return entities



def ner_task_core(sentence: str) -> Dict[str, List[str]]:
    """NER识别核心逻辑"""
    sentence_obj = Sentence(sentence)
    flair_tagger.predict(sentence_obj)
    result = {label: [] for label in LABELS}

    for entity in sentence_obj.get_spans('ner'):
        if entity.tag in LABELS:
            result[entity.tag].append(entity.text)

    return result


@app.route("/api/tools/ner_recognize", methods=["POST"])
def ner_recognize_api():
    """
    Dify调用的NER识别接口
    请求格式：{"sentences": ["句子1", "句子2"]}
    返回格式：适配Dify的JSON结构
    """
    try:
        # 获取请求体
        data = request.get_json()
        if not data or "sentences" not in data:
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "请求参数缺失：必须包含sentences字段"
            }), 400

        # 执行NER识别（批量处理句子）
        sentences = data["sentences"]
        if not isinstance(sentences, list):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "sentences必须是列表类型"
            }), 400

        ner_results = []
        for sentence in sentences:
            ner_results.append(ner_task_core(sentence))

        # 返回结果（适配Dify）
        return jsonify({
            "status": "success",
            "data": {
                "ner_results": ner_results
            },
            "message": "NER识别成功"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": {},
            "message": f"NER识别失败：{str(e)}"
        }), 500

from comparison.metrics import MetricsCalculation
@app.route("/api/tools/calculate_metrics", methods=["POST"])
def calculate_metrics_api():
    """
    Dify调用的指标计算接口
    请求格式：
    {
        "expected_entities": [{label1: [ent1, ent2], label2: [...]}, ...],
        "predicted_entities": [{label1: [ent1, ent2], label2: [...]}, ...]
    }
    """
    try:
        # 获取请求体
        data = request.get_json()
        # 参数校验
        if not data or "expected_entities" not in data or "predicted_entities" not in data:
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "请求参数缺失：必须包含expected_entities和predicted_entities字段"
            }), 400

        expected = data["expected_entities"]
        predicted = data["predicted_entities"]
        # 类型校验
        if not isinstance(expected, list) or not isinstance(predicted, list):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": "expected_entities和predicted_entities必须是列表类型"
            }), 400
        # 长度校验
        if len(expected) != len(predicted):
            return jsonify({
                "status": "failed",
                "data": {},
                "message": f"真实标签数量({len(expected)})与预测结果数量({len(predicted)})不匹配"
            }), 400

        # 计算指标
        metrics = MetricsCalculation.calculate(expected, predicted)

        # 返回结果（适配Dify）
        return jsonify({
            "status": "success",
            "data": metrics,
            "message": "指标计算成功"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "data": {},
            "message": f"指标计算失败：{str(e)}"
        }), 500

# ===================== 测试入口 =====================
if __name__ == "__main__":
    # 启动Flask服务，默认端口5000（避免和FastAPI端口冲突）
    app.run(host="0.0.0.0", port=5003, debug=True)