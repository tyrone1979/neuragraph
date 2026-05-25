# 节点名称和连接线修复

## 修复日期
2026-05-25

## 修复的问题

### 1. START 和 END 节点连接线缺失 ✅

**问题描述**：
- START 节点到第一个节点的连接线没有显示
- 最后一个节点到 END 节点的连接线没有显示

**原因**：
- 代码中过滤掉了 START 和 END 的连接
- 缺少自动创建 START/END 连接的逻辑

**解决方案**：
```javascript
// 修改了 loadExistingGraph 函数
// 1. 移除了过滤 START/END 连接的代码
// 2. 添加了自动创建 START -> firstNode 和 lastNode -> END 的连接

// Also create START -> firstNode and lastNode -> END connections if they don't exist
const realNodes = nodes.filter(n => n !== 'START' && n !== 'END');
if (realNodes.length > 0) {
    const firstNode = realNodes[0];
    const lastNode = realNodes[realNodes.length - 1];
    
    // Check if START -> firstNode edge exists
    const hasStartConnection = edges.some(e => 
        e[0] === 'START' || (Array.isArray(e[0]) && e[0].includes('START'))
    );
    if (!hasStartConnection && graph.getCell('START')) {
        createSimpleLink('START', firstNode);
    }
    
    // Check if lastNode -> END edge exists
    const hasEndConnection = edges.some(e => 
        e[1] === 'END' || (Array.isArray(e[1]) && e[1].includes('END'))
    );
    if (!hasEndConnection && graph.getCell('END')) {
        createSimpleLink(lastNode, 'END');
    }
}
```

### 2. Agent 节点名称显示为 "UNKNOWN" ✅

**问题描述**：
- biomed_ner_graph 中的 agent 节点名称没有正确显示
- 显示为 "UNKNOWN" 或空白

**原因**：
- 当 agent 数据不存在时，nodeData 被设置为 null
- `data?.name` 返回 undefined
- 导致节点标题显示不正确

**解决方案**：
```javascript
// 修改了 createNode 函数
let nodeName = config.label;
if (type === 'start') {
    nodeName = 'START';
} else if (type === 'end') {
    nodeName = 'END';
} else if (type === 'agent' || type === 'subgraph' || type === 'tool') {
    // Try to get name from data or use node ID
    if (data && data.name) {
        nodeName = data.name;
    } else if (id) {
        nodeName = id;  // 使用节点 ID 作为备选名称
    }
}
```

同时修改了 loadExistingGraph 函数，确保即使 agent 不存在也传递正确的数据：

```javascript
// Build nodeData even if agent doesn't exist (use node ID as name)
const nodeData = {
    id: nodeId,
    name: agent?.name || nodeId,  // 使用节点 ID 作为备选
    inputs: agent?.inputs || [],
    outputs: agent?.outputs ? [agent.outputs.name] : ['output'],
    type: agent?.type || 'LLM',
    model: agent?.model || '',
    prompt_template: agent?.prompt_template || null,
    persistence: agent?.persistence || null,
    tools: agent?.tools || []
};
```

## 修改的文件

- `ui/static/js/graph_visual_editor.js`
  - `loadExistingGraph()` 函数：添加 START/END 连接逻辑
  - `createNode()` 函数：改进节点名称显示
  - `loadExistingGraph()` 函数：确保总是传递完整的 nodeData

## 测试方法

访问以下 URL 进行测试：
- http://localhost:5001/graph/biomed_ner_graph/edit
- http://localhost:5001/graph/bio_ner_graph/edit

应该能够看到：
- ✅ START 节点连接到第一个节点
- ✅ 最后一个节点连接到 END 节点
- ✅ 所有 Agent 节点显示正确的名称（而不是 UNKNOWN）
