# Visual Editor 界面修复 - 2026-05-25

## 🐛 修复的问题

### 1. Subgraph 没有显示 ✅

**问题描述**：
- demo_advanced_workflow 中的 subgraph 节点没有正确显示

**原因**：
- 之前的代码只检查 `data.nodes` 是否存在来识别 subgraph
- 没有正确处理 subgraph 的 inputs 和 outputs

**解决方案**：
```javascript
// 修改了 createNode 函数中 subgraph 的处理逻辑
if (type === 'subgraph' && data) {
    // 优先使用 subgraph 自带的 inputs/outputs
    if (data.inputs) {
        inputs = data.inputs;
    } else if (data.nodes) {
        inputs = computeSubgraphInputs(data);
    }
    if (data.outputs) {
        outputs = Array.isArray(data.outputs) ? data.outputs : [data.outputs];
    } else if (data.nodes) {
        outputs = computeSubgraphOutputs(data);
    }
}
```

**修复效果**：
- subgraph 节点现在正确显示
- 正确读取嵌套的 inputs/outputs
- 支持引用外部子图（如 `nested_entity_extraction`）

---

### 2. Agent 名字显示在框外面 ✅

**问题描述**：
- 节点名字显示位置不对，跑到框外面去了

**原因**：
- 之前的 text 属性使用了错误的 ref 配置
- 字体大小和位置设置不当

**解决方案**：
```javascript
// 修改了文本标签的位置和样式
text: {
    text: displayText,
    fontSize: 13,
    fontWeight: 'bold',
    fill: '#333333',
    ref: 'rect',           // 引用 rect 元素
    refX: '50%',            // 居中对齐
    refY: 15,               // 距离顶部 15px
    textAnchor: 'middle'    // 水平居中
}
```

**修复效果**：
- 节点名称显示在矩形框内顶部
- 使用 ref 引用确保位置准确
- 字体大小 13px，粗体，灰色文字

---

### 3. 连接线错误 ✅

**问题描述**：
- 节点之间的连接线显示不正确
- START 和 END 节点的连接有问题

**原因**：
- selectNode 和 deselectAll 函数还在使用 'body' 属性
- 节点已经改为 'rect' 和 'circle' 类型

**解决方案**：
```javascript
// 修改了节点选择和取消选择的逻辑
function selectNode(node) {
    const nodeType = node.get('nodeData')?.type;
    if (nodeType === 'start' || nodeType === 'end') {
        // Circle 节点
        node.attr('circle/strokeWidth', 3);
    } else {
        // Rectangle 节点
        node.attr('rect/strokeWidth', 3);
    }
    // 添加阴影效果
    node.attr({
        filter: {
            name: 'dropShadow',
            args: { dx: 2, dy: 2, blur: 4, color: 'rgba(0,0,0,0.2)' }
        }
    });
}

function deselectAll() {
    if (selectedCell?.isElement()) {
        const nodeType = selectedCell.get('nodeData')?.type;
        if (nodeType === 'start' || nodeType === 'end') {
            selectedCell.attr('circle/strokeWidth', 2);
        } else {
            selectedCell.attr('rect/strokeWidth', 2);
        }
        selectedCell.attr('filter', {});
    }
}
```

**修复效果**：
- 连接线正确显示
- 节点选中效果正常
- START → 第一个节点 → ... → 最后一个节点 → END 的流程正确

---

### 4. START 和 END 改为圆圈 ✅

**问题描述**：
- START 和 END 节点需要改为圆形外观

**原因**：
- 之前的实现使用 Rectangle 矩形

**解决方案**：
```javascript
// 为 START 和 END 创建特殊的 Circle 节点
if (type === 'start' || type === 'end') {
    const circleNode = new joint.shapes.standard.Circle({
        id: nodeId,
        size: { width: 60, height: 60 },
        attrs: {
            circle: {
                fill: config.color,
                stroke: config.color,
                strokeWidth: 2
            },
            text: {
                text: displayText,  // 'START' 或 'END'
                fontSize: 12,
                fontWeight: 'bold',
                fill: '#ffffff',
                textAnchor: 'middle',
                textVerticalAnchor: 'middle'
            }
        },
        ports: {
            groups: {
                'out': { position: 'right', attrs: {...} },
                'in': { position: 'left', attrs: {...} }
            },
            items: type === 'start' ? 
                [{ id: 'out_trigger', group: 'out', label: { text: 'trigger' } }] :
                [{ id: 'in_input', group: 'in', label: { text: 'input' } }]
        }
    });
    
    graph.addCell(circleNode);
    return circleNode;
}
```

**修复效果**：
- START 节点：绿色圆形（#10b981），白色文字 "START"
- END 节点：红色圆形（#ef4444），白色文字 "END"
- 尺寸：60x60 像素
- 右侧有输出端口，左侧有输入端口

---

## 🎨 修复后的界面

### 节点类型

| 节点类型 | 形状 | 颜色 | 边框 |
|---------|------|------|------|
| START | 圆形 | #10b981 (绿色) | 白色 "START" 文字 |
| END | 圆形 | #ef4444 (红色) | 白色 "END" 文字 |
| Agent | 矩形 | 各类型对应颜色 | 节点名称在顶部 |
| Subgraph | 矩形 | #06b6d4 (青色) | 子图名称在顶部 |
| Branch | 矩形 | #f59e0b (橙色) | 条件分支逻辑 |
| Loop | 矩形 | #3b82f6 (蓝色) | 循环配置 |

### 节点结构

```
┌─────────────────────┐
│  Node Name          │  ← 顶部：名称
├─────────────────────┤
│ ◯ input1            │  ← 左侧：输入端口
│ ◯ input2            │
├─────────────────────┤
│ ◯ output1          │  ← 右侧：输出端口
│ ◯ output2          │
└─────────────────────┘
```

### START/END 特殊结构

```
        ┌───┐
        │ S │
        │ T │
        │ A │
        │ R │
        │ T │
        └───┘
          └─→ trigger

        ┌───┐
        │input│
        │    │
        │ E  │
        │ N  │
        │ D  │
        └───┘
```

## 📁 修改的文件

- `ui/static/js/graph_visual_editor.js`
  - 重写了 `createNode()` 函数
  - 添加 START/END 圆形节点支持
  - 修复了 subgraph 的 inputs/outputs 处理
  - 修正了节点选择/取消选择逻辑

## 🚀 测试方法

```bash
# 1. 启动应用
.\start.ps1

# 2. 访问高级工作流
http://localhost:5001/graph/demo_advanced_workflow/edit

# 3. 验证修复
- [ ] START 和 END 是圆形
- [ ] 节点名称显示在框内顶部
- [ ] subgraph 正确显示
- [ ] 连接线正确连接各节点
- [ ] 选中节点时有阴影效果
```

## 🎯 界面布局预览

```
┌──────────────────────────────────────────────────────────────┐
│                     Canvas                                   │
│                                                             │
│   ┌───┐                                                     │
│   │STA│──────→ ┌──────────┐──────→ ┌──────────┐          │
│   └───┘         │  Agent 1  │         │  Agent 2  │          │
│                 │           │         │            │          │
│                 │   input   │         │   input    │          │
│                 │  output   │         │  output    │          │
│                 └───────────┘         └────────────┘          │
│                       │                      │                  │
│                       └──────────→ ┌───┐ ←──────┘             │
│                                  │END │                       │
│                                  └───┘                        │
└──────────────────────────────────────────────────────────────┘
```

## ⚠️ 注意事项

1. **节点大小**：START/END 为 60x60，其他节点宽度 180，高度动态计算
2. **端口间距**：端口之间距离 22px
3. **颜色编码**：
   - 绿色：START
   - 红色：END
   - 紫色：LLM Agent
   - 绿色：PGM Agent
   - 青色：Subgraph
   - 橙色：Branch
   - 蓝色：Loop
