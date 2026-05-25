# Visual Editor 功能增强

## 更新日期
2026-05-25

## 新增功能

### 1. 右键菜单功能 ✅

#### 在空白画布处右键
- **Create Agent**: 在点击位置创建新的 Agent 节点
- **Create Subgraph**: 在点击位置创建新的 Subgraph 节点
- **Export as SVG**: 导出为 SVG 格式
- **Export as PNG**: 导出为 PNG 格式（2x 分辨率）
- **Fit to Content**: 自适应内容
- **Reset View**: 重置视图

#### 在节点处右键
- **Edit Properties**: 编辑节点属性
- **Delete Node**: 删除节点
- **Connect From Here**: 从此节点开始连接
- **Connect To Here**: 连接到此节点

**实现方式**:
```javascript
paper.el.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    const clientX = e.clientX;
    const clientY = e.clientY;
    
    const localPoint = paper.clientToLocalPoint({ x: clientX, y: clientY });
    const cellView = paper.findViewAt(localPoint);
    
    if (cellView && cellView.model.isElement()) {
        selectNode(cellView.model);
        showNodeContextMenu(clientX, clientY, cellView.model);
    } else {
        showBlankContextMenu(clientX, clientY, localPoint);
    }
});
```

### 2. 导出功能 ✅

#### SVG 导出
- 克隆当前画布 SVG
- 计算边界框并添加 padding
- 设置正确的 viewBox 和尺寸
- 使用 XMLSerializer 序列化
- 下载为 `.svg` 文件

#### PNG 导出
- 基于 SVG 导出
- 转换为 Canvas
- 2x 分辨率提升清晰度
- 白色背景填充
- 下载为 `.png` 文件

**实现代码**:
```javascript
function downloadGraphAsSVG() {
    const svgElement = paper.svg.cloneNode(true);
    const bbox = graph.getBBox();
    // ... 克隆和设置 viewBox
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);
    // ... 下载逻辑
}

function downloadGraphAsPNG() {
    const svgElement = paper.svg.cloneNode(true);
    const canvas = document.createElement('canvas');
    const scale = 2; // 2x for better quality
    canvas.width = (bbox.width + padding * 2) * scale;
    canvas.height = (bbox.height + padding * 2) * scale;
    // ... 转换为 Canvas 并下载
}
```

### 3. 属性面板保存和恢复功能 ✅

#### 保存按钮
- 收集所有可编辑字段的值
- 解析嵌套字段路径（如 `prompt_template.description`）
- 更新内存中的 agent 数据
- 更新画布上的节点显示
- 通过 AJAX 保存到后端
- 保存历史记录

#### 恢复按钮
- 恢复到原始数据
- 重新渲染属性面板
- 不保存到后端（仅重置）

**实现代码**:
```javascript
function saveNodeChanges(agentId) {
    const originalData = window['originalAgentData_' + agentId];
    const updatedData = JSON.parse(JSON.stringify(originalData));
    
    $('#typeSpecificProps .editable-field').each(function() {
        const $field = $(this);
        const fieldPath = $field.data('field');
        let value = $field.val();
        // ... 解析字段路径并更新数据
    });
    
    // 更新后端
    $.ajax({
        url: '/agents/api/save',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(updatedData),
        success: function(response) {
            alert('Agent saved successfully!');
        }
    });
}

function resetNodeChanges(agentId) {
    const originalData = window['originalAgentData_' + agentId];
    // 重新渲染属性面板
    renderTypeSpecificProps(nodeData, originalData);
}
```

### 4. LLM Prompt 编辑功能 ✅

#### 可编辑字段
所有 LLM Agent 的配置现在都可以编辑：

1. **Model**: 模型名称
2. **Inputs**: 输入字段（逗号分隔）
3. **Outputs**: 
   - Name: 输出名称
   - Type: 输出类型
4. **Persistence**:
   - File Path: 文件路径
   - File Type: 文件类型

#### Prompt Template（可编辑）
- **Description**: 描述
- **System Prompt**: 系统提示词
- **Human Prompt**: 用户提示词
- **Relation Schema**:
  - Head Type: 头实体类型
  - Tail Type: 尾实体类型

**实现方式**:
```javascript
// 可编辑字段使用 editable-field 类
<input type="text" class="form-control form-control-sm editable-field" 
       data-field="model" value="${agent.model || ''}">

// 嵌套字段使用点号路径
<textarea class="form-control form-control-sm editable-field" 
          data-field="prompt_template.system" rows="4">
    ${prompt.system || ''}
</textarea>
```

## 界面改进

### 右键菜单样式
- 圆角卡片设计
- 阴影效果
- 图标+文字布局
- 悬停高亮
- 分隔线分组

### 属性面板
- 卡片式布局
- 颜色编码（蓝色标题）
- "Editable" 标签提示
- 保存/恢复按钮
- 响应式表单

## 使用说明

### 右键创建 Agent
1. 在画布空白处右键
2. 选择 "Create Agent"
3. 输入 Agent ID
4. 节点将出现在点击位置

### 导出图片
1. 右键点击画布
2. 选择 "Export as SVG" 或 "Export as PNG"
3. 文件将自动下载

### 编辑 Agent 属性
1. 点击选中节点
2. 在右侧属性面板查看信息
3. 修改字段值
4. 点击 "Save Changes" 保存
5. 或点击 "Reset to Original" 恢复

### 编辑 Prompt
1. 选中 LLM Agent
2. 滚动到 "Prompt Template" 卡片
3. 编辑 Description、System Prompt、Human Prompt
4. 保存更改

## 修改的文件

- `ui/static/js/graph_visual_editor.js`
  - 添加右键菜单功能
  - 添加导出 SVG/PNG 功能
  - 添加属性保存/恢复功能
  - 添加 Prompt 编辑功能

## 测试方法

```bash
# 启动应用
.\start.ps1

# 访问工作流
http://localhost:5001/graph/bio_ner_graph/edit
```

**测试步骤**:
1. 右键画布，尝试导出功能
2. 右键画布，尝试创建新 Agent
3. 选中一个 LLM Agent
4. 编辑 Prompt Template
5. 点击 "Save Changes"
6. 验证数据是否保存

## 注意事项

- 导出 PNG 时使用 2x 分辨率，文件较大但清晰度更好
- 保存 Agent 会通过 AJAX 调用 `/agents/api/save` 端点
- Prompt 编辑支持嵌套字段（用点号分隔）
- 右键菜单会自动在点击位置显示，可能超出屏幕
