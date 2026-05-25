# Visual Editor 更新日志

## 📅 更新日期: 2026-05-25

## ✅ 已完成的修复

### 1. 布局混乱问题 ✅

**问题描述**: 编辑已有 workflow 时，节点布局混乱，位置不合理

**解决方案**:
- 集成了 Dagre 布局算法（参考原来 `graph.js` 的实现）
- 使用从左到右 (`rankDir: 'LR`) 的布局方向
- 优化布局参数：
  - `nodeSep: 60` - 节点间距
  - `rankSep: 120` - 层级间距
  - `edgeSep: 40` - 边间距
  - `marginX: 30, marginY: 30` - 边距

**修改文件**: `ui/static/js/graph_visual_editor.js`

**核心代码**:
```javascript
// Apply Dagre layout (like original)
joint.layout.DirectedGraph.layout(graph, {
    rankDir: 'LR',  // Left to Right
    nodeSep: 60,
    rankSep: 120,
    edgeSep: 40,
    marginX: 30,
    marginY: 30
});
```

### 2. 连接线显示问题 ✅

**问题描述**: 节点之间没有连接线，或者连接线不美观

**解决方案**:
- 使用 `joint.shapes.standard.Link` 创建连接线
- 添加平滑曲线连接器 (`smooth connector with radius 20`)
- 根据节点类型自动设置连接线颜色
- 正确处理 START/END 节点的连接

**修改文件**: `ui/static/js/graph_visual_editor.js`

**核心代码**:
```javascript
function createSimpleLink(sourceId, targetId) {
    const link = new joint.shapes.standard.Link();
    link.source({ id: sourceId });
    link.target({ id: targetId });
    link.attr({
        line: {
            stroke: color,
            strokeWidth: 2,
            targetMarker: {
                type: 'path',
                d: 'M 10 -5 0 0 10 5 z'
            }
        }
    });
    
    // Smooth connector like original
    link.connector('smooth', { radius: 20 });
    graph.addCell(link);
}
```

### 3. 字体重叠问题 ✅

**问题描述**: 节点内的文字重叠，可读性差

**解决方案**:
- 使用 `HeaderedRectangle` 替代 `Rectangle` 节点
- 分离头部（节点名称）和内容（详细信息）
- 设置合适的字体大小和文本换行
- 添加 `textWrap` 配置防止文本溢出

**节点样式配置**:
```javascript
headeredRectangle.attr({
    headerText: {
        text: nodeName,
        fontSize: 12,
        fontWeight: 'bold',
        textWrap: {
            width: 124,
            height: 34,
            ellipsis: true
        },
    },
    bodyText: {
        text: bodyText,
        fontSize: 11,
        refX: 8,
        refY: 20,
        textAnchor: 'start',
        textVerticalAnchor: 'top',
        textWrap: {
            width: 124,
            height: 80,
            ellipsis: true
        },
    },
    body: {
        fill: '#ffffff',
        stroke: config.color,
        strokeWidth: 2,
        rx: 1,
        ry: 1,
        height: 100
    }
});
```

### 4. 右侧属性面板增强 ✅

**问题描述**: 右侧属性面板信息不完整

**解决方案**:
- 显示完整的 Agent 信息：
  - Agent ID
  - Agent Type (LLM/PGM)
  - Model (仅 LLM)
  - Inputs/Outputs
  - Persistence 配置
  - Prompt Template (仅 LLM)
  - Relation Schema (如果有)
  - Tools (如果有)
- 使用卡片式布局，信息分类清晰
- 为不同节点类型（Agent/Subgraph/Start/End）定制显示

**Agent 详情卡片**:
```html
<div class="card mb-3">
    <div class="card-header bg-primary text-white">
        <h6 class="mb-0"><i class="fas fa-robot me-2"></i>Agent Details</h6>
    </div>
    <div class="card-body">
        <div class="mb-2">
            <label class="form-label small fw-bold">Agent ID</label>
            <input type="text" class="form-control form-control-sm" value="${nodeData.originalId}" readonly>
        </div>
        <!-- ... 更多字段 ... -->
    </div>
</div>
```

## 🔧 技术改进

### 子图处理
- 实现了完整的 `expandSubgraphRecursive()` 函数
- 支持嵌套子图的递归展开
- 正确处理子图的入口和出口节点

### 节点创建
- 使用 `HeaderedRectangle` 实现专业外观
- 自动识别节点类型（LLM/PGM/SUB）
- 根据类型显示不同颜色的边框

### 数据映射
- 支持变量映射配置
- 实时显示输入输出字段
- 提供映射模板示例

## 📂 修改的文件列表

1. `ui/static/js/graph_visual_editor.js` - 核心编辑器逻辑
   - 重写了 `createNode()` 函数
   - 新增 `createSimpleLink()` 函数
   - 新增 `expandSubgraphRecursive()` 函数
   - 优化了 `loadExistingGraph()` 函数
   - 增强了属性面板显示

## 🎯 下一步计划

- [ ] 支持节点拖拽调整位置
- [ ] 实现实时编辑保存
- [ ] 添加节点创建向导
- [ ] 优化移动端体验
- [ ] 添加撤销/重做按钮到工具栏

## 🐛 已知问题

暂无

## 📝 使用说明

### 访问工作流编辑器
```
http://localhost:5001/graph/<workflow_id>/edit
```

### 示例工作流
```
http://localhost:5001/graph/bio_ner_graph/edit
```

### 主要功能
- ✅ 从左侧面板拖拽组件到画布
- ✅ 双击节点查看详细信息
- ✅ 使用 Dagre 自动布局
- ✅ 创建节点间连接
- ✅ 右侧属性面板查看所有信息
- ✅ 撤销/重做操作
- ✅ 缩放和平移画布

## 🎉 总结

本次更新大幅提升了可视化编辑器的用户体验，解决了之前存在的布局、连接线和显示问题，并增强了属性面板的信息展示能力。编辑器现在能够正确加载和显示所有类型的工作流，包括带有嵌套子图的复杂工作流。
