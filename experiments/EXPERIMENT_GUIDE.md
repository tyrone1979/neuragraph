# NeuraGraph 药理学性能评估实验指南
## BC5CDR (BioCreative V) 化学-疾病关系提取

---

## 1. 实验概述

### 1.1 实验目标
在药理学领域对 NeuraGraph 进行完整的性能评估，证明系统在生物医学 NLP 任务中的有效性。

### 1.2 数据集: BC5CDR
- **来源**: BioCreative V CDR (Chemical-Disease Relation) Task
- **规模**: 测试集 500 篇 PubMed 摘要
- **标注**: 
  - Chemical entities (化学物质, MeSH ID)
  - Disease entities (疾病, MeSH ID)  
  - Chemical-Induced-Disease (CID) relations
- **格式**: PubTator (已有 parser: `data/data_parser.py`)

### 1.3 评估任务

| 任务 | 描述 | 评估级别 |
|------|------|----------|
| **Task 1: Chemical NER** | 识别文本中的化学物质实体 | Entity-level (Exact Match) |
| **Task 2: Disease NER** | 识别文本中的疾病实体 | Entity-level (Exact Match) |
| **Task 3: CID Relation** | 提取化学-疾病诱导关系 | Relation-level (Pair Match) |

### 1.4 评估指标

$$Precision = \frac{TP}{TP + FP}, \quad Recall = \frac{TP}{TP + FN}, \quad F1 = 2 \cdot \frac{Precision \cdot Recall}{Precision + Recall}$$

- **Micro**: 全局计算 TP/FP/FN（适用于类别不平衡）
- **Macro**: 每篇文章单独计算后取平均（适用于评估稳定性）

---

## 2. 实验方法

### 2.1 Method A: NeuraGraph (LLM-based Pipeline)

使用已有的 `ner_4_doc_graph` 工作流：

```
START → sentence_split → sub_ner(metrics) → END
                    ↑___________________|
```

其中 `sub_ner` 展开为：
```
START → bio_ner → END
```

**组件说明**:
- `sentence_split`: 将文档拆分为句子
- `sub_ner` (SUB): 对每句调用 `bio_ner` (Flair PGM)
- `bio_ner`: HunFlair2 句级 NER；workflow `bindings` 将 `expected_entities` 传入 metrics

**Prompt 模板** (bio_ner):
```
Task: Extract all chemical and disease entities from the biomedical text.
Output format: {"chemicals": ["entity1", ...], "diseases": ["entity1", ...]}
```

### 2.2 Method B: Flair HunFlair2 Baseline

使用 Flair 的 HunFlair2 NER 模型（BioNER 专用）:

```python
from flair.nn import Classifier
tagger = Classifier.load("hunflair2")
# 直接对文本进行 NER，提取 Chemical 和 Disease 实体
```

### 2.3 Relation Extraction

**NeuraGraph**: 使用 `make_relations` agent 从提取的实体对中预测 CID 关系

**Baseline**: 基于共现的规则方法（同一句子中的 chemical-disease 对视为相关）

---

## 3. 实验步骤

### Step 1: 准备数据集 (已完成)
```bash
# 数据集已在 testsets/bio_ner/test.txt
# 包含 500 篇文献，格式: PubTator
# 每篇包含: title, abstract, entities, relations
```

### Step 2: 配置实验参数

编辑 `meta/exps/<exp_id>.json`:
```json
{
  "exp_id": "bc5cdr_eval_202501",
  "name": "BC5CDR Pharmacological Evaluation",
  "runner_id": "bio_ner_graph",
  "runner_type": "graph",
  "dataset": "test.txt",
  "status": "new"
}
```

### Step 3: 运行实验

#### 3.1 启动 NeuraGraph
```bash
export LLM_KEY=<your_openai_key>
python -m ui.app  # 启动 Flask 服务
```

#### 3.2 创建实验 (通过 UI)
1. 打开 http://localhost:5001/experiments/new
2. 选择 Runner: `bio_ner_graph`
3. 选择 Dataset: `test.txt`
4. 点击 "Start Experiment"

#### 3.3 批量运行 (通过 API)
```bash
# 创建实验配置
curl -X POST http://localhost:5001/exp/api/save \
  -H "Content-Type: application/json" \
  -d '{
    "exp_id": "bc5cdr_llm_eval",
    "name": "BC5CDR LLM NER Evaluation",
    "runner_id": "bio_ner_graph",
    "runner_type": "graph",
    "dataset": "test.txt"
  }'

# 启动批量实验
curl -N http://localhost:5001/stream/run/bc5cdr_llm_eval
```

#### 3.4 运行 Baseline (Flair)
```bash
python experiments/run_baseline_flair.py \
  --input testsets/bio_ner/test.txt \
  --output results/baseline_flair.json
```

### Step 4: 评估结果

```bash
# 评估 NeuraGraph 结果
python experiments/evaluate.py \
  --gold testsets/bio_ner/test.txt \
  --pred results/bc5cdr_llm_eval.json \
  --output results/evaluation_llm.json

# 评估 Baseline 结果
python experiments/evaluate.py \
  --gold testsets/bio_ner/test.txt \
  --pred results/baseline_flair.json \
  --output results/evaluation_baseline.json
```

### Step 5: 生成报告

```bash
# 通过 API 自动生成报告
curl -N http://localhost:5001/stream/report/bc5cdr_llm_eval

# 或通过脚本生成对比报告
python experiments/generate_report.py \
  --methods results/evaluation_llm.json results/evaluation_baseline.json \
  --output report/bc5cdr_comparison.md
```

---

## 4. 预期输出

### 4.1 评估结果格式
```json
{
  "task1_chemical_ner": {
    "micro": {"precision": 0.82, "recall": 0.78, "f1": 0.80},
    "macro": {"precision": 0.81, "recall": 0.77, "f1": 0.79}
  },
  "task2_disease_ner": {
    "micro": {"precision": 0.85, "recall": 0.80, "f1": 0.82},
    "macro": {"precision": 0.84, "recall": 0.79, "f1": 0.81}
  },
  "task3_cid_relation": {
    "micro": {"precision": 0.58, "recall": 0.52, "f1": 0.55},
    "macro": {"precision": 0.56, "recall": 0.50, "f1": 0.53}
  }
}
```

### 4.2 对比报告

| Method | Chemical F1 | Disease F1 | CID F1 | Runtime |
|--------|-------------|------------|--------|---------|
| NeuraGraph (GPT-4o) | 0.80 | 0.82 | 0.55 | ~30min |
| Flair HunFlair2 | 0.88 | 0.86 | N/A | ~5min |
| Rule-based RE | N/A | N/A | 0.42 | ~1min |

---

## 5. 论文写作建议

### 5.1 实验设计亮点
1. **标准化 Benchmark**: 使用 BioCreative V (BC5CDR)，公认的生物医学 NER/RE 标准数据集
2. **多任务评估**: NER (Chemical + Disease) + Relation Extraction (CID)
3. **与 SOTA 对比**: Flair HunFlair2 (BioNER 领域 SOTA)
4. **定量分析**: Micro/Macro F1, Precision, Recall
5. **消融实验**: 可以测试不同 LLM (GPT-4o vs GPT-3.5 vs DeepSeek)

### 5.2 关键论点
- **NeuraGraph 的优势**: 
  - 无需训练数据（zero-shot）
  - 可配置的工作流（通过编辑 graph 调整 pipeline）
  - 统一平台（NER + RE 在同一个 workflow 中完成）
- **权衡**: 
  - LLM 方法比专用 NER 模型略低，但无需领域训练
  - 运行时间更长（API 调用），但可通过本地模型优化

### 5.3 审稿人可能关注的问题
1. **为什么 F1 比 Flair 低？** → LLM 是通用模型，Flair 是 BioNER 专用训练模型
2. **运行时间？** → 提供详细的运行时分析，讨论批处理和本地部署优化
3. **可重复性？** → 提供完整的实验配置、prompt 模板、随机种子

---

## 6. 文件清单

```
experiments/
  EXPERIMENT_GUIDE.md          # 本指南
  run_baseline_flair.py        # Flair 基线运行脚本
  run_experiment.py            # 批量实验运行脚本
  evaluate.py                  # 评估脚本 (NER + RE)
  generate_report.py           # 报告生成脚本
  configs/
    bc5cdr_llm.json            # LLM 实验配置
    bc5cdr_baseline.json       # 基线实验配置
```
