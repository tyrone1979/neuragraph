# Advanced Workflow Demo - 使用说明

## 📋 概述

已创建一个包含 **Branch**（分支）、**Loop**（循环）、**Subgraph**（子图）的高级工作流示例：

**文件位置**: `meta/graphs/demo_advanced_workflow.json`

## 🎯 工作流架构图

```
[START] → [Text Input] → [Sentence Split] → [Process Loop] → [Analysis Branch]
                                                           ↓
                                      ┌───────────────────┴───────────────────┐
                                      ▼                                       ▼
                              [NER Subgraph]                           [RE Subgraph]
                                      │                                       │
                                      └───────────────────┬───────────────────┘
                                                          ▼
                                                    [Aggregator] → [END]
```

## 🔧 节点说明

| 节点 | 类型 | 功能 |
|------|------|------|
| Text Input | Agent (LLM) | 输入待处理的文本 |
| Sentence Split | Agent (PGM) | 将文本分割成句子列表 |
| Process Loop | Loop | 遍历每个句子（ForEach 模式） |
| Analysis Branch | Branch | 根据内容类型路由：实体识别或关系抽取 |
| NER Subgraph | Subgraph | 命名实体识别子图 |
| RE Subgraph | Subgraph | 关系抽取子图 |
| Aggregator | Agent (PGM) | 汇总结果 |

## 🔀 Branch 分支逻辑

```
条件判断：
├─ contains_entities(item) → 路由到 NER Subgraph
└─ contains_relations(item) → 路由到 RE Subgraph
```

## 🔄 Loop 循环配置

```json
{
  "loopType": "foreach",
  "array": "{{ sentence_split.sentences }}"
}
```

- **Loop Type**: ForEach（遍历数组）
- **Input**: 从 Sentence Split 输出的句子列表
- **Behavior**: 对每个句子执行后续逻辑

## 📂 Subgraph 子图

| 子图 ID | 功能 |
|---------|------|
| `sub_ner` | 命名实体识别 |
| `sub_re` | 关系抽取 |

## 🔗 变量映射示例

```
sentence_split.text = {{ text_input.text }}
process_loop.items = {{ sentence_split.sentences }}
ner_agent.text = {{ analysis_branch.item }}
aggregator.entities = {{ ner_agent.entities }}
aggregator.relations = {{ re_agent.relations }}
```

## 🚀 如何使用

### 1. 启动应用

```powershell
.\start.ps1
```

### 2. 访问工作流编辑器

打开浏览器访问: `http://localhost:5001/graph/demo_advanced_workflow/edit`

### 3. 查看工作流

画布将自动加载完整的工作流图，包含：
- 🟢 Start 节点
- 🟣 Agent 节点
- 🟡 Branch 节点
- 🔵 Loop 节点
- 🔷 Subgraph 节点
- 🔴 End 节点

### 4. 测试运行

点击顶部 "Test" 按钮，输入测试数据：

```json
{
  "text": "The drug aspirin has been shown to reduce inflammation and may interact with warfarin, increasing bleeding risk."
}
```

## 📝 工作流执行流程

1. **输入阶段**: 用户提供文本输入
2. **分割阶段**: 文本被分割成句子
3. **循环阶段**: 遍历每个句子
4. **分支阶段**: 判断句子类型（实体 vs 关系）
5. **处理阶段**: 调用相应子图处理
6. **汇总阶段**: 整合所有结果

## 🎨 可视化提示

- 每个节点类型有不同颜色标识
- 端口显示输入/输出变量名称
- 连线显示数据流向
- 点击节点可查看详细配置

## 📁 相关文件

- `meta/graphs/demo_advanced_workflow.json` - 工作流定义
- `meta/graphs/sub_ner.json` - NER 子图
- `meta/graphs/sub_re.json` - RE 子图
- `meta/agents/sentence_split.json` - 句子分割 Agent
