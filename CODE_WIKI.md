# NeuraGraph Code Wiki

## 目录
1. [项目概述](#项目概述)
2. [架构设计](#架构设计)
3. [核心模块](#核心模块)
4. [关键类与函数](#关键类与函数)
5. [数据流程](#数据流程)
6. [配置与元数据格式](#配置与元数据格式)
7. [插件系统](#插件系统)
8. [实验与评估](#实验与评估)
9. [API接口](#api接口)
10. [运行方式](#运行方式)

---

## 项目概述

### 简介
NeuraGraph 是一个轻量级平台，用于构建基于 LLM 的智能体工作流，专注于生物医学文本挖掘任务，包括：
- 命名实体识别 (NER) - 如化学物质、疾病识别
- 关系抽取 (RE) - 如化学-疾病关联
- 共指消解
- 同义词/上位词提取
- 依存句法分析
- 三元组转换

### 技术栈
- **后端**: Python 3.12+ + Flask
- **前端**: Bootstrap 5 + JointJS
- **工作流引擎**: 自定义轻量级 DAG (未来可能迁移到 LangGraph)
- **LLM 集成**: OpenAI, Ollama, 自定义端点等
- **数据持久化**: JSON 元数据 + 结果存储 (可选 PostgreSQL 用于工作流状态)

---

## 架构设计

### 系统架构图
```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Agent 管理   │  │  Graph 编辑   │  │  Experiment 运行  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        API 层                                │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌─────────────────┐ │
│  │ Agent API│ │Graph API │ │LLM API │ │Experiment API   │ │
│  └──────────┘ └──────────┘ └────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       服务实体层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ AgentEntity  │  │ GraphEntity  │  │    Runner        │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       元数据层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ MetaLoader   │  │ GraphMeta    │  │    TestLoader    │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       插件系统                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │PGMExecutor   │  │Checkpointer  │  │  MetricsPlugin   │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构
```
.
├── comparison/           # 对比代码（自定义 vs Dify工具）
├── data/                 # 数据解析器
│   └── data_parser.py    # 数据解析核心类
├── doc/                  # 文档
├── experiments/          # 实验脚本
│   ├── evaluate.py       # 评估脚本
│   ├── generate_report.py # 报告生成
│   ├── run_baseline_flair.py # Flair 基线
│   └── run_experiment.py # 实验运行
├── meta/                 # 元数据目录
│   ├── agents/           # Agent 配置 JSON
│   ├── graphs/           # Workflow 配置 JSON
│   ├── llms/             # LLM 配置 JSON
│   ├── tools/            # 工具配置 JSON
│   ├── exps/             # 实验历史 JSON
│   └── tests/            # 测试数据
├── plugin/               # 插件系统
│   ├── plugin_loader.py  # 插件加载器
│   └── plugins.py        # 插件定义
├── service/              # 核心服务
│   ├── api/              # API 服务
│   │   └── terminal.py   # 终端执行 API
│   ├── entity/           # 实体模型
│   │   ├── agent.py      # Agent 实体
│   │   ├── entity.py     # 基类
│   │   ├── graph.py      # Graph 实体
│   │   ├── runner.py     # 执行器
│   │   └── tool.py       # 工具实体
│   └── meta/             # 元数据加载
│       └── loader.py     # 元数据加载器
├── tests/                # 运行时测试数据
├── ui/                   # UI 层
│   ├── components/       # 组件
│   ├── static/           # 静态资源
│   ├── templates/        # Jinja2 模板
│   ├── __init__.py
│   ├── agent_api.py      # Agent API Blueprint
│   ├── app.py            # Flask 主应用
│   ├── experiment_api.py # 实验 API
│   ├── graph_api.py      # Graph API
│   ├── llm_api.py        # LLM API
│   └── ...
├── utils/                # 工具函数
├── autogen.py            # 自动生成脚本
├── chat.py               # 聊天界面
├── requirements.txt      # 依赖
├── run.sh                # 启动脚本
└── run_workflow.py       # 终端 workflow 执行入口
```

---

## 核心模块

### 1. 服务实体层 ([service/entity/](file:///d:/projects/agentic_llmre/service/entity))

#### Entity 基类 ([entity.py](file:///d:/projects/agentic_llmre/service/entity/entity.py))
所有可执行实体的基类，定义了统一的接口。

```python
class Entity:
    def __init__(self, meta: Dict[str, Any], checkpointer: Checkpointer = None):
        self.metadata = meta
        self.checkpointer = checkpointer
    
    def invoke(self, state: T) -> Dict[str, Any]:
        """同步执行"""
        pass
    
    async def ainvoke(self, state: T, **kwargs):
        """异步执行"""
        pass
    
    def stream(self, state: T, **kwargs) -> Iterator[dict[str, Any] | Any]:
        """流式执行"""
        pass
    
    def get_state(self, config):
        """获取状态"""
        pass
```

#### AgentEntity ([agent.py](file:///d:/projects/agentic_llmre/service/entity/agent.py))
智能体实体，支持三种类型：
- **LLM**: 调用语言模型
- **PGM**: 执行 Python 代码
- **SUB**: 迭代执行子图

**核心方法**:
- `invoke(state)`: 同步执行 agent
- `stream(state, **kwargs)`: 流式输出
- `execute_process(code_string, state)`: 安全执行 PGM 代码
- `_persistence(dir, file_name, payload)`: 数据持久化

#### GraphEntity ([graph.py](file:///d:/projects/agentic_llmre/service/entity/graph.py))
工作流图实体，使用 LangGraph 的 StateGraph 构建 DAG。

**核心方法**:
- `invoke(state)`: 同步执行完整 workflow
- `stream(state, **kwargs)`: 流式执行
- `_call_agent(name)`: 调用单个 agent（支持 SUB 子图）

#### ToolLoader ([tool.py](file:///d:/projects/agentic_llmre/service/entity/tool.py))
工具加载器，动态从代码字符串创建 StructuredTool。

**核心函数**:
- `_create_input_schema(tool_id, parameters)`: 从 JSON Schema 动态创建 Pydantic 模型
- `_exec_code_to_func(code)`: 从代码字符串提取函数

#### RunnerLoader ([runner.py](file:///d:/projects/agentic_llmre/service/entity/runner.py))
统一执行器加载器，根据 ID 智能分发到 Agent 或 Graph。

---

### 2. 元数据层 ([service/meta/loader.py](file:///d:/projects/agentic_llmre/service/meta/loader.py))

#### MetaLoader
元数据加载器，管理所有 JSON 配置文件。

**核心方法**:
- `load(name, id)`: 加载单个配置
- `loads(name)`: 加载所有配置
- `dump(name, id, data)`: 保存配置
- `delete(name, id)`: 删除配置
- `exists(name, id)`: 检查配置是否存在

#### GraphMetaLoader
图元数据加载器，支持加载子图。

---

### 3. 插件系统 ([plugin/](file:///d:/projects/agentic_llmre/plugin))

#### Plugin 基类
所有插件继承自此类。

#### 内置插件

1. **PGMExecutor**: PGM 代码安全执行环境
   - `safe_builtins`: 允许的内置函数白名单
   - `safe_import`: 模块导入白名单

2. **MemoryCheckpointer**: 内存状态持久化
   - 提供 `InMemorySaver`

3. **(可选) PostgresCheckpointer**: PostgreSQL 状态持久化
   - 提供 `PostgresSaver` 和 `AsyncPostgresSaver`

4. **Metrics**: 指标计算插件
   - `MetricsCalculation.calculate(expected, predicted)`: 计算 P/R/F1
   - `compute_micro_macro(metrics)`: 计算微平均和宏平均

---

## 关键类与函数

### AgentEntity.invoke()

```
输入: state (TypedDict)
流程:
  ├─ 若 type == "PGM":
  │   └─ execute_process(process, state)
  │       └─ 返回 __result__
  │
  └─ 若 type == "LLM":
      ├─ 从 state 提取 inputs 字段
      ├─ 渲染 prompt_template
      ├─ 调用 LLM
      └─ 返回结果
输出: { outputs.name: 结果 }
```

**位置**: [agent.py:195](file:///d:/projects/agentic_llmre/service/entity/agent.py#L195)

---

### GraphEntity.invoke()

```
输入: state
流程:
  ├─ 构建 StateGraph
  ├─ 按 edges 顺序执行 nodes
  │   └─ 对每个 node: _call_agent(name)
  │       └─ 若 agent.type == "SUB":
  │           └─ 迭代执行子图
  │
  └─ 返回最终 state
输出: 完整 state dict
```

**位置**: [graph.py:38](file:///d:/projects/agentic_llmre/service/entity/graph.py#L38)

---

### _call_agent()

处理单个节点调用，支持 SUB 子图迭代。

```python
def _call_agent(name: str):
    agent = AgentLoader.load(name)
    if agent is None:
        return lambda s: s  # passthrough
    
    if agent.type != "SUB":
        return lambda s: agent.invoke(s)
    else:
        # SUB: 迭代执行子图
        subgraph = GraphLoader.load(name)
        def invoke(s):
            inputs = s[agent.inputs[0]]
            results = None
            for inp in inputs:
                sub_state = dict(s)
                # 注入迭代变量
                for idx in agent.idx:
                    sub_state[idx] = inp[idx] if dict else inp
                # 调用子图
                out = subgraph.invoke(sub_state)
                output = out[agent.outputs['name']]
                # 聚合结果
                ...
            return {agent.outputs['name']: results}
        return invoke
```

**位置**: [graph.py:93](file:///d:/projects/agentic_llmre/service/entity/graph.py#L93)

---

### MetaLoader.load()

```python
@staticmethod
def load(name: str, id: str) -> Dict[str, Any] | None:
    path = _get_path(name) / f"{id}.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["id"] = id  # 注入 ID
        return cfg
    except FileNotFoundError:
        return None
```

**位置**: [loader.py:18](file:///d:/projects/agentic_llmre/service/meta/loader.py#L18)

---

### TerminalRunner.run()

终端统一执行入口，智能分发到 Agent 或 Graph。

**位置**: [terminal.py:21](file:///d:/projects/agentic_llmre/service/api/terminal.py#L21)

---

## 数据流程

### Workflow 执行流程

```
1. 初始输入 state
   ↓
2. GraphEntity.compile()
   └─ 构建 StateGraph，添加 nodes/edges
   ↓
3. GraphEntity.invoke(state)
   └─ LangGraph 按 DAG 执行
      ↓
   4. 每个 node 调用 _call_agent(name)
      ├─ 若为普通 Agent: agent.invoke(state)
      │  ├─ LLM: prompt + LLM 调用
      │  └─ PGM: 安全执行 Python 代码
      │
      └─ 若为 SUB Agent:
         ├─ 从 state[inputs[0]] 获取迭代列表
         ├─ 对每个元素:
         │  ├─ 构建子图 state (注入 idx 变量)
         │  └─ 递归调用 subgraph.invoke(sub_state)
         └─ 聚合结果
      ↓
   5. 最终 state 传递到下一个 node
      ↓
6. 返回最终 state
```

### State 传递规则
- 每个 agent 从 `state` 读取 `inputs` 字段
- 每个 agent 写入 `state[outputs.name]`
- PGM agent 通过 `state['field']` 读取，`__result__ = ...` 写入
- SUB agent 迭代 `inputs[0]`，通过 `idx` 注入循环变量

---

## 配置与元数据格式

### Agent 配置格式 ([meta/agents/](file:///d:/projects/agentic_llmre/meta/agents))

**文件命名**: `{agent_id}.json`

#### LLM Agent
```json
{
  "name": "Agent 名称",
  "type": "LLM",
  "inputs": ["field1", "field2"],
  "outputs": { "name": "result_field", "type": "str|list|dict" },
  "persistence": {
    "file_path": "path/to/save",
    "file_type": "csv|json|jsonl|txt",
    "columns": ["col1", "col2"]
  },
  "model": "llm_config_id",
  "prompt_template": {
    "description": "描述",
    "system": "系统提示词",
    "human": "用户提示词，使用 {field} 占位符"
  },
  "tools": ["tool1_id", "tool2_id"],
  "created_at": "2026-01-01T00:00:00"
}
```

**示例**: [sentence_split.json](file:///d:/projects/agentic_llmre/meta/agents/sentence_split.json)

#### PGM Agent
```json
{
  "name": "Agent 名称",
  "type": "PGM",
  "inputs": ["field1", "field2"],
  "outputs": { "name": "result_field", "type": "dict" },
  "persistence": {},
  "process": "Python 代码，使用 state 读取，__result__ 输出",
  "created_at": "2026-01-01T00:00:00"
}
```

**示例**: [bio_ner.json](file:///d:/projects/agentic_llmre/meta/agents/bio_ner.json)

#### SUB Agent
```json
{
  "name": "Agent 名称",
  "type": "SUB",
  "inputs": ["iterable_field"],
  "outputs": { "name": "results", "type": "list" },
  "persistence": {},
  "idx": ["loop_var1", "loop_var2"],
  "created_at": "2026-01-01T00:00:00"
}
```

---

### Graph 配置格式 ([meta/graphs/](file:///d:/projects/agentic_llmre/meta/graphs))

**文件命名**: `{graph_id}.json`

```json
{
  "id": "graph_id",
  "name": "Workflow 名称",
  "description": "描述",
  "nodes": ["START", "agent1", "sub_graph", "END"],
  "edges": [
    ["START", "agent1"],
    ["agent1", "sub_graph"],
    ["sub_graph", "END"]
  ],
  "created_at": "2026-01-01T00:00:00"
}
```

**子图**: 若 node ID 以 `sub_` 开头，会被识别为子图。

**示例**: [bio_ner_graph.json](file:///d:/projects/agentic_llmre/meta/graphs/bio_ner_graph.json)

---

### LLM 配置格式 ([meta/llms/](file:///d:/projects/agentic_llmre/meta/llms))

**文件命名**: `{llm_id}.json`

```json
{
  "id": "llm_id",
  "type": "openai|ollama|custom",
  "model": "model-name",
  "base_url": "https://api.example.com/v1",
  "api_key": "sk-...",
  "temperature": 0.7,
  "max_tokens": 1000,
  "timeout": 300,
  "max_retries": 3,
  "rate_limit": 60
}
```

**示例**: [kimi-2.6.json](file:///d:/projects/agentic_llmre/meta/llms/kimi-2.6.json)

---

### Tool 配置格式 ([meta/tools/](file:///d:/projects/agentic_llmre/meta/tools))

```json
{
  "id": "tool_id",
  "name": "工具名称",
  "description": "描述",
  "parameters": {
    "type": "object",
    "properties": {
      "param1": { "type": "string", "description": "..." },
      "param2": { "type": "integer", "description": "..." }
    },
    "required": ["param1"]
  },
  "code": "def func(param1, param2):\n    ...\n    return result"
}
```

---

## 插件系统

### 开发新插件

在 [plugins.py](file:///d:/projects/agentic_llmre/plugin/plugins.py) 中继承 `Plugin` 类:

```python
class MyPlugin(Plugin):
    def load(self):
        """同步加载，返回 {name: object} dict"""
        my_obj = SomeObject()
        return {"my_plugin": my_obj}
    
    async def aload(self):
        """异步加载 (可选)"""
        pass
```

### 使用插件

在代码中通过 `plugin_loader.get_plugin(name)` 获取:

```python
from plugin.plugin_loader import get_plugin

my_plugin = get_plugin("my_plugin")
```

在 PGM agent 中通过 `get_plugin(name)` 访问:

```python
# PGM process 代码
my_plugin = get_plugin("my_plugin")
result = my_plugin.do_something()
__result__ = result
```

---

## 实验与评估

### 实验运行 ([experiments/run_experiment.py](file:///d:/projects/agentic_llmre/experiments/run_experiment.py))

支持多种模式:

```bash
# 1. 完整流程: NeuraGraph + 基线 + 评估 + 报告
python experiments/run_experiment.py \
    --full \
    --workflow bio_ner_graph \
    --dataset testsets/bio_ner/test.txt \
    --output-prefix results/bc5cdr

# 2. 仅运行 NeuraGraph
python experiments/run_experiment.py \
    --workflow bio_ner_graph \
    --dataset testsets/bio_ner/test.txt \
    --output results/neuragraph.json

# 3. 仅运行基线
python experiments/run_experiment.py --baseline --dataset ...

# 4. 仅评估已有结果
python experiments/run_experiment.py --evaluate --gold ... --pred ...
```

### 评估脚本 ([experiments/evaluate.py](file:///d:/projects/agentic_llmre/experiments/evaluate.py))

支持三个任务:
- **Task 1**: Chemical NER
- **Task 2**: Disease NER  
- **Task 3**: CID Relation Extraction

```bash
python experiments/evaluate.py \
    --gold testsets/bio_ner/test.txt \
    --pred results/neuragraph.json \
    --output results/evaluation.json \
    --task all
```

输出格式:
```json
{
  "task1_chemical_ner": {
    "micro": {"precision": 0.85, "recall": 0.80, "f1": 0.82},
    "macro": {"precision": 0.84, "recall": 0.79, "f1": 0.81},
    "num_documents": 100
  },
  "task2_disease_ner": { ... },
  "task3_cid_relation": { ... }
}
```

---

## API 接口

### Flask App ([ui/app.py](file:///d:/projects/agentic_llmre/ui/app.py))

主应用入口，注册所有 Blueprint。

### Agent API ([ui/agent_api.py](file:///d:/projects/agentic_llmre/ui/agent_api.py))
- `GET /agents`: 列出所有 agent
- `GET /agents/<id>`: 获取 agent
- `POST /agents`: 创建 agent
- `PUT /agents/<id>`: 更新 agent
- `DELETE /agents/<id>`: 删除 agent
- `POST /agents/<id>/run`: 执行 agent

### Graph API ([ui/graph_api.py](file:///d:/projects/agentic_llmre/ui/graph_api.py))
- `GET /graphs`: 列出所有 graph
- `GET /graphs/<id>`: 获取 graph
- `POST /graphs`: 创建 graph
- `PUT /graphs/<id>`: 更新 graph
- `DELETE /graphs/<id>`: 删除 graph
- `POST /graphs/<id>/run`: 执行 graph

### LLM API ([ui/llm_api.py](file:///d:/projects/agentic_llmre/ui/llm_api.py))
- LLM 配置管理

### Experiment API ([ui/experiment_api.py](file:///d:/projects/agentic_llmre/ui/experiment_api.py))
- 实验运行与管理

### Stream API ([ui/stream_api.py](file:///d:/projects/agentic_llmre/ui/stream_api.py))
- SSE 流式输出

---

## 运行方式

### 1. Web 界面

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python ui/app.py
# 或
bash run.sh

# 访问
http://localhost:5001
```

**首次使用**:
1. "LLMs" 标签页 → 添加 LLM 配置
2. "Agents" 标签页 → 浏览/创建 agent
3. "Workflows" 标签页 → 打开示例 graph
4. "Datasets" 标签页 → 上传测试数据
5. "Experiments" 标签页 → 选择 graph + dataset → 运行

### 2. 命令行

```bash
# 列出可用 agent/graph
python run_workflow.py --list-agents
python run_workflow.py --list-graphs

# 执行 workflow
python run_workflow.py \
    --graph bio_ner_graph \
    --input '{"text": "这是一段生物医学摘要..."}' \
    --verbose

# 执行单个 agent
python run_workflow.py \
    --agent sentence_split \
    --input '{"text": "..."}'
```

### 3. Python API

```python
from service.api.terminal import TerminalRunner

runner = TerminalRunner(verbose=True)

# 运行 graph
result = runner.run("bio_ner_graph", {"text": "..."})
if result["status"] == "success":
    print(result["result"])

# 运行 agent
result = runner.run_agent("sentence_split", {"text": "..."})
```

---

## 常见模式

### 模式 1: 文档级 NER Pipeline
```
[START] → sentence_split → sub_ner → merge → metrics → [END]
                          ↑
                     sub_ner (子图，对每个句子执行 bio_ner)
```

### 模式 2: LLM + 规则混合
```
[START] → llm_ner → rule_filter → refine → [END]
```

### 模式 3: 迭代处理 (SUB Agent)
```
graph: process_list
  nodes: [START, sub_process_item, END]
  edges: [[START, sub_process_item], [sub_process_item, END]]

sub_agent: sub_process_item
  type: SUB
  inputs: ["items"]
  idx: ["item"]
  (引用子图 sub_process_item_graph)

sub_graph: sub_process_item_graph
  nodes: [START, process_one, END]
```

---

## 依赖关系

### requirements.txt
```
numpy
langchain
langgraph
langchain-ollama
ollama
tqdm~=4.67.1
Flask[async]~=3.1.2
flask-sse
pydantic
langchain[openai]
# flair (可选)
# psycopg[binary,pool] (可选，PostgreSQL)
```

### 核心依赖说明
- **Flask**: Web 框架
- **LangChain**: LLM 应用开发框架
- **LangGraph**: 状态图执行引擎
- **JointJS**: 前端图编辑器
- **Bootstrap**: UI 框架
- **(可选) Flair**: BioNLP 工具包
- **(可选) psycopg**: PostgreSQL 驱动

---

## 安全注意事项

1. **PGM 执行**: PGM agent 代码在限制环境中执行，仅允许安全的内置函数和导入
2. **API Key**: LLM API Key 存储在 `meta/llms/` JSON 文件中，注意保密
3. **用户输入**: 来自前端的输入应在 PGM 中谨慎处理

---

## 扩展指南

### 添加新的 LLM 提供商

在 [agent.py:50](file:///d:/projects/agentic_llmre/service/entity/agent.py#L50) 添加新类型:

```python
if llm_type == "my_provider":
    self.model = MyProviderLLM(...)
```

### 添加新的数据解析器

在 `data/data_parser.py` 继承 `DataParser`:

```python
class MyDataParser(DataParser):
    def __init__(self, text: str):
        super().__init__(text)
        # 解析逻辑
```

---

## 参考文档

- [MANUAL.md](doc/MANUAL.md) - 用户操作手册
- [CODE_GUIDELINES.md](doc/CODE_GUIDELINES.md) - 代码规范
- [README.md](README.md) - 项目说明
- [SKILL.md](SKILL.md) - AutoGen 技能文档

