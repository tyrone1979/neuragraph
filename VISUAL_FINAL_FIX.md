# Visual Editor 完整修复 - 2026-05-25

## 🐛 修复的 4 个 Bug

### 1. 右键菜单完整功能 ✅

**修复内容**：
- 空白处右键：Create Agent / Create Subgraph / Create Branch / Create Loop / Export SVG / Export PNG / Fit to Content / Reset View
- 节点处右键：Edit Properties / Copy Node / Delete Node
- 菜单完全重新实现，使用 `fixed` 定位 + `z-index: 10000` 确保不会隐藏
- 点击外部自动关闭菜单

### 2. 点击节点属性面板 ✅

**修复内容**：
- `hidePropertyPanel()` 现在正确给 `#propertyPanel` 添加 `d-none`
- `showPropertyPanel()` 正确从节点 `nameText/text` 或 `text/text` 读取名称
- 属性面板默认隐藏，点击节点才显示
- 关闭按钮和点击空白均能关闭面板

### 3. Dify 风格节点显示 ✅

**改进内容**：
- 节点显示更多信息：名称 + 模型名 / 类型标签
- 边框颜色区分类型：
  - 紫色(#8b5cf6) - Agent 节点
  - 青色(#06b6d4) - Subgraph 节点  
  - 橙色(#f59e0b) - Branch 节点
  - 蓝色(#3b82f6) - Loop 节点
  - 粉色(#ec4899) - Tool 节点
  - LLM Agent 边框有 indigo 色 badge，PGM Agent 有绿色 badge
- 连接线通过端口连接，端口标注变量名称
- 端口标签使用 `outside` 定位，清晰可见

### 4. Subgraph 和嵌套 Subgraph ✅

**修复内容**：
- `loadExistingGraph()` 优先读取 `visualData.nodes[].type` 确定节点类型
- 正确区分 subgraph/branch/loop/agent 节点
- subgraph 节点携带 `nodes` 和 `edges` 数据用于后续展开
- `nested_entity_extraction` 嵌套子图在 demo 工作流中原位显示

## 📁 修改的文件

| 文件 | 变更 |
|------|------|
| `ui/static/js/graph_visual_editor.js` | **完全重写** - 精简至 ~820 行，修复所有 bug |
| `ui/agent_api.py` | 添加 `POST /agents/api/save` 端点 |
| `ui/graph_api.py` | 简化 list 端点（无需额外 save_graph 端点） |
| `ui/static/css/graph.css` | 添加 `.bg-indigo`, `.bg-cyan` 样式 |

## 🎨 节点外观

```
┌──────────────────┐
│  Agent Name      │  ← 13px bold, 居中对齐
│  [LLM]           │  ← badge 标签
│  gpt-4           │  ← 模型名（10px gray）
├──────────────────┤
│ ◯ text          │  ← 输入端口（左）
│ ◯ query         │
├──────────────────┤
│ ◯ answer        │  ← 输出端口（右）
└──────────────────┘
```

## 🚀 测试

```bash
.\start.ps1
# 测试 bio_ner_graph
http://localhost:5001/graph/bio_ner_graph/edit
# 测试 subgraph 工作流
http://localhost:5001/graph/demo_advanced_workflow/edit
```
