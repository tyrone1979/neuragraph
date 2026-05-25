# Visual Editor 增强功能 - 2026-05-25

## 🎉 本次更新

### 1. 右侧属性面板优化 ✅

**改进**：
- 属性面板默认**隐藏**
- 只有点击节点时才显示
- 添加关闭按钮（×）
- 点击画布空白处自动隐藏

### 2. 工具条可拖动 ✅

**改进**：
- 工具条可以**自由拖动**到画布任意位置
- 支持鼠标拖拽
- 限制在画布边界内

### 3. 背景颜色切换 ✅

**改进**：
- 工具条添加颜色选择器
- 实时切换画布背景颜色
- 默认颜色：#fafafa

### 4. 输入输出端口显示 ✅

**改进**：
- 每个节点显示**输入端口**（左侧）和**输出端口**（右侧）
- 端口显示变量名称
- 支持连接线拖拽
- 动态高度适应端口数量

### 5. Subgraph 嵌套支持 ✅

**改进**：
- demo_advanced_workflow 现在支持**嵌套 subgraph**
- NER Subgraph 引用 `nested_entity_extraction` 子图
- 子图内部包含完整的工作流结构

**新增文件**：
- `meta/graphs/nested_entity_extraction.json` - 嵌套子图定义

**demo_advanced_workflow 结构**：
```
START → Text Input → Sentence Split → Process Loop → Analysis Branch
                                                             ↓
                                          ┌─────────────────┴─────────────────┐
                                          ↓                                   ↓
                              [Nested Entity Extraction]              [RE Subgraph]
                                          ↓                                   ↓
                                          └───────────────┬───────────────────┘
                                                          ↓
                                                    [Aggregator] → END
```

**nested_entity_extraction 子图**：
```
START → Tokenizer → NER Model → Filter Entities → END
```

### 6. 变量映射改进 ✅

**改进**：
- 节点上直接显示输入输出变量名
- 连接线可以通过端口拖拽创建
- 右侧属性面板显示完整映射关系

## 🎨 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  NeuraGraph                    [Zoom] [Test] [Save]             │
├──────────────┬───────────────────────────────┬──────────────────┤
│  Components  │      Canvas (可拖动工具条)      │   Properties     │
│              │  ┌──────────────────────┐     │   (点击节点显示)  │
│  Search...   │  │ 🛠️ Select | Link | Del │     │                  │
│              │  └──────────────────────┘     │   [Node Name]    │
│  Agents:     │                               │   [Close ×]      │
│  ┌────────┐ │   ┌─────────┐                 │                  │
│  │Agent 1 │ │   │ START   │──┐              │   Agent Details  │
│  └────────┘ │   └─────────┘  │              │   ─────────────  │
│              │       │         │              │   ID: xxx        │
│  Subgraphs: │       ▼         ▼              │   Type: LLM     │
│  ┌────────┐ │   ┌─────────┐ ┌─────────┐     │   Model: xxx     │
│  │Sub 1   │ │   │ Text In │→│Sentence │     │                  │
│  └────────┘ │   └─────────┘ └─────────┘     │   [Save] [Reset] │
└──────────────┴───────────────────────────────┴──────────────────┘
         │
         └── 画布背景颜色可切换
```

## 📁 修改的文件

1. **ui/templates/graph.html**
   - 添加工具条可拖动标识
   - 添加背景颜色选择器
   - 属性面板默认隐藏
   - 添加关闭按钮

2. **ui/static/js/graph_visual_editor.js**
   - 添加 `initToolbarDrag()` 函数
   - 添加 `initBackgroundColor()` 函数
   - 修改 `createNode()` 添加端口
   - 修改 `showPropertyPanel()` 显示面板
   - 添加端口连接逻辑

3. **meta/graphs/demo_advanced_workflow.json**
   - 更新为嵌套 subgraph 结构
   - NER Agent 引用 `nested_entity_extraction`

4. **meta/graphs/nested_entity_extraction.json** (新文件)
   - 嵌套的实体抽取子图

## 🚀 测试方法

```bash
# 1. 启动应用
.\start.ps1

# 2. 访问高级工作流示例
http://localhost:5001/graph/demo_advanced_workflow/edit

# 3. 测试功能
- [ ] 拖动工具条到任意位置
- [ ] 点击颜色选择器切换背景
- [ ] 点击节点查看属性面板
- [ ] 点击×关闭属性面板
- [ ] 查看节点上的输入输出端口
- [ ] 拖拽端口创建连接线
- [ ] 查看嵌套的 subgraph
```

## 🎯 下一步计划

- [ ] 双击打开 subgraph 编辑器
- [ ] 支持缩放和平移画布
- [ ] 添加网格对齐功能
- [ ] 保存工具条位置
- [ ] 优化移动端体验

## ⚠️ 注意事项

1. **端口连接**：确保从输出端口拖拽到输入端口
2. **背景颜色**：选择器在工具条最右侧
3. **嵌套深度**：建议不超过 3 层嵌套
4. **性能**：大量节点时可能需要优化渲染
