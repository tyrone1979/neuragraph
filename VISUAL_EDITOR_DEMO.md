# NeuraGraph 可视化编辑器使用演示

## 🎉 新功能概述

已实现类似 Dify 的可视化工作流编辑器，支持：

1. **拖拽式组件添加** - 从左侧面板拖拽组件到画布
2. **可视化节点连接** - 通过端口连接节点，支持变量映射
3. **分支条件 (Branch)** - if/else 条件逻辑
4. **循环节点 (Loop)** - for/while/foreach 循环
5. **子图 (Subgraph)** - 支持嵌套子图
6. **属性配置面板** - 右侧面板配置节点属性
7. **撤销/重做** - 历史记录支持
8. **测试运行** - 直接在界面测试工作流

## 📁 新增文件

- `ui/templates/graph.html` - 完全重构的可视化编辑器界面
- `ui/static/js/graph_visual_editor.js` - 新的编辑器逻辑
- `ui/static/css/graph.css` - 样式增强

## 🚀 使用说明

### 启动应用

```bash
python ui/app.py
# 访问 http://localhost:5001
```

### 创建新工作流

1. 访问 "Workflows" 页面
2. 点击 "New Workflow" 或编辑现有工作流
3. 使用左侧组件面板拖拽节点到画布

### 组件类型

| 类型 | 描述 | 颜色 |
|------|------|------|
| Start | 工作流起点 | 绿色 |
| End | 工作流终点 | 红色 |
| Agent | LLM Agent 节点 | 紫色 |
| Subgraph | 子图引用 | 青色 |
| Tool | 工具调用 | 粉色 |
| Branch | 条件分支 | 橙色 |
| Loop | 循环控制 | 蓝色 |

### 变量映射

每个 Agent 节点可以在右侧属性面板配置输入映射：

```
输入名: {{ 前一个节点.输出名 }}
```

例如：
```
query: {{ start.text }}
context: {{ retrieve.documents }}
```

### 分支条件 (Branch)

Branch 节点支持多个条件分支：

1. 选中 Branch 节点
2. 在右侧面板添加/编辑条件
3. 使用 Jinja2 语法：`{{ score }} > 0.8`
4. 连接不同分支到不同后续节点

### 循环节点 (Loop)

Loop 节点支持三种循环模式：

- **For 循环**：指定迭代次数
- **While 循环**：指定条件表达式
- **ForEach 循环**：遍历数组

### 测试工作流

1. 点击顶部 "Test" 按钮
2. 在弹窗左侧输入 JSON 数据
3. 点击 "Run" 查看执行追踪

## 📊 示例工作流

### 示例 1: 基础问答

```
[Start] → [Retrieve] → [Generate] → [End]
```

### 示例 2: 带分支的问答

```
[Start] → [Classify] → [Branch]
                      ↓
          [IsQuestion?] ┬ Yes → [Answer]
                      └ No  → [Search] → [Answer]
                                           ↓
                                         [End]
```

### 示例 3: 循环处理

```
[Start] → [Split Documents] → [Loop]
                              ↓
                       [Process One Doc] → [End]
```

## 🔌 数据格式

### 保存的 Graph 数据结构

```json
{
  "id": "my_workflow",
  "name": "My Workflow",
  "description": "Description",
  "nodes": ["node1", "node2"],
  "edges": [["node1", "node2"]],
  "visualData": {
    "nodes": [
      {
        "id": "agent_1",
        "type": "agent",
        "originalId": "existing_agent",
        "position": {"x": 100, "y": 200},
        "data": {
          "inputs": ["query"],
          "outputs": ["answer"],
          "mappings": {
            "query": "{{ start.text }}"
          }
        }
      }
    ],
    "links": []
  }
}
```

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Z | 撤销 |
| Ctrl+Shift+Z | 重做 |
| Ctrl+S | 保存 |
| Delete | 删除选中 |

## 🎨 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo] NeuraGraph     [Zoom In] [Fit] [Zoom Out] [Test] [Save] │
├──────────────┬───────────────────────────────┬──────────────────┤
│  Components  │                               │   Properties     │
│              │         Canvas                │                  │
│  [Start]     │                               │  [Node Name]     │
│  [End]       │   ┌──────┐     ┌──────┐      │                  │
│  [Branch]    │   │Start │───▶ │Agent │      │  Inputs:         │
│  [Loop]      │   └──────┘     └──────┘      │    query: ___    │
│              │      │            │          │  Outputs:        │
│  Agents:     │      ▼            ▼          │    answer        │
│  ┌────────┐ │   ┌──────┐     ┌──────┐      │                  │
│  │Agent 1 │ │   │Branch│     │ End  │      │  [Branch Cond]   │
│  └────────┘ │   └──────┘     └──────┘      │  [Loop Config]   │
│  ┌────────┐ │                               │                  │
│  │Agent 2 │ │  [Select] [Connect] [Delete]  │                  │
│  └────────┘ │  [Undo]   [Redo]              │                  │
└──────────────┴───────────────────────────────┴──────────────────┘
```

## 🐛 调试提示

如果遇到问题：

1. 打开浏览器开发者工具 (F12)
2. 查看 Console 标签页的错误信息
3. 确保所有必需的 API 端点正常响应

## 📝 注意事项

- 当前版本兼容旧格式 Graph
- 可视化数据保存在 `visualData` 字段中
- 端口连接会自动验证有效性
