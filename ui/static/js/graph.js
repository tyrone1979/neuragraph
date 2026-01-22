const DRAWER_WIDTH = 500;       // 抽屉宽度
const HANDLE_VISIBLE = 20;      // 关闭时露出的把手宽度
const minZoom = 0.2, maxZoom = 3;   // ← 提前定义
let isDrawerOpen = false;

let currentGraph = null;  //edit mode current graph data
if (graphsById && current) {
    currentGraph = graphsById[current];

} else {
    currentGraph = {
        id: '',  // 保险
        description: '',
        name: '',
        nodes: [],
        edges: []
    };

}


// 全局
let subgraphRanges = {};

// 节点样式配置

const nodeStyles = {
    startEnd: { stroke: '#17a2b8', bodyColor: '#ffffff' }, // 蓝框
    PGM: { stroke: '#28a745', bodyColor: '#ffffff' }, // 绿框
    LLM: { stroke: '#4b6cb7', bodyColor: '#ffffff' }, // 蓝灰框
    SUB: { stroke: '#764ba2', bodyColor: '#ffffff' }  // 紫框
};

// 页面加载完成
$(document).ready(function () {
    // 渲染初始工作流
    initJointJS();
    if (currentGraph.id) {
        renderWorkflow(currentGraph);
    }
    initUI();                          // 我们自己的 UI 初始化
});


function zoomClamped(delta) {
    const s = paper.scale();
    const newS = Math.max(minZoom, Math.min(maxZoom, s.sx + delta));
    paper.scale(newS, newS);
}


function resetView() {
    paper.scale(1, 1);
    paper.translate(0, 0);
}


// 右键菜单
const $contextMenu = $('<div>', {
    id: 'customContextMenu',
    css: {
        position: 'absolute',
        background: '#fff',
        border: '1px solid #ccc',
        boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
        display: 'none',
        zIndex: 1000,
        padding: '5px 0'
    }
}).appendTo('body');

function showContextMenu(x, y, items) {
    $contextMenu.empty();
    $.each(items, function (_, item) {
        $('<div>')
            .text(item.label)
            .css({
                padding: '5px 20px',
                cursor: 'pointer'
            })
            .on('mouseover', function () { $(this).css('background', '#f0f0f0'); })
            .on('mouseout', function () { $(this).css('background', '#fff'); })
            .on('click', function () {
                item.action();
                hideContextMenu();
            })
            .appendTo($contextMenu);
    });
    $contextMenu.css({ left: x + 'px', top: y + 'px', display: 'block' });
}

function hideContextMenu() {
    $contextMenu.hide();
}


function toggleDrawer(open) {
    if (open === undefined) open = !isDrawerOpen;
    isDrawerOpen = open;

    const $sidebar = $('#leftSidebar');
    const $handle = $('#drawerHandle');
    const $icon = $('#handleIcon');

    if (isDrawerOpen) {
        $sidebar.css('transform', 'translateX(0)');
        $handle.css('left', DRAWER_WIDTH + 'px');
        $icon.css('transform', 'rotate(180deg)');
    } else {
        $sidebar.css('transform', `translateX(-${DRAWER_WIDTH - HANDLE_VISIBLE}px)`);
        $handle.css('left', HANDLE_VISIBLE + 'px');
        $icon.css('transform', 'rotate(0deg)');
    }
}

// 统一初始化所有 UI 交互（减少函数数量）
function initUI() {
    // 缩放按钮
    $('#zoomIn').on('click', () => zoomClamped(0.2));
    $('#zoomOut').on('click', () => zoomClamped(-0.2));
    $('#fitToContent').on('click', fitToContent);
    $('#resetView').on('click', resetView);

    // 抽屉把手点击
    $('#drawerHandle').on('click', (e) => {
        e.stopPropagation();
        toggleDrawer();
    });

    // 鼠标靠近左侧自动打开
    $(document).on('mousemove', (e) => {
        if (e.clientX <= 40 && !isDrawerOpen) {
            toggleDrawer(true);
        }
    });

    // 鼠标离开抽屉后延迟收起
    $('#leftSidebar').on('mouseleave', () => {
        if (isDrawerOpen) {
            setTimeout(() => {
                if (!$('#leftSidebar').is(':hover') && !$('#drawerHandle').is(':hover')) {
                    toggleDrawer(false);
                }
            }, 800);
        }
    });

    // 点击画布收起抽屉
    $('#paper_panel').on('click', () => {
        if (isDrawerOpen) toggleDrawer(false);
    });

    // 全局点击或滚动隐藏右键菜单
    $(document).on('click scroll', hideContextMenu);

    // 窗口 resize 时自动适配
    $(window).on('resize', fitToContent);


    $('#nodesList').on('click', '.remove-node', function (e) {
        e.preventDefault();
        e.stopPropagation();

        // 尝试多种方式获取 nodeId（兼容模板渲染的各种情况）
        const $nodeItem = $(this).closest('.node-item');
        let nodeId = $nodeItem.data('index')
        if(nodeId){
            if (!confirm('Are you sure you want to delete this node? All associated edges will also be deleted.')) {
                return;
            }
            removeNode(nodeId);
            renderForm();
            renderWorkflow(currentGraph);
        }
        $nodeItem.remove();


    });

    // ---------- 全局 suggestions 管理（防遮挡 + 多输入框正常） ----------
    let $currentSuggestions = null;
    let $currentInput = null;  // 记住当前输入框

    $('#nodesList').on('input', 'input', function (e) {
        const $input = $(this);
        const q = $input.val().trim();
        const oldValue = $input.data('node-id');  // 直接拿原始 runner id

       // 找到同级的 ul（无论它现在在哪）
        let $suggestions = $input.data('suggestions-ul');  // 用 data 缓存关联
        if (!$suggestions || $suggestions.length === 0) {
            $suggestions = $input.next('ul.suggestions');
            if ($suggestions.length === 0) return;
            $input.data('suggestions-ul', $suggestions);  // 缓存
        }

        // 隐藏旧的（如果换了输入框）
        if ($currentSuggestions && $currentInput && $currentInput[0] !== $input[0]) {
            $currentSuggestions.hide();
        }

        $currentSuggestions = $suggestions.empty().hide();
        $currentInput = $input;

        if (q.length < 2) return;

        // 关键：移到 body，脱离抽屉
        $suggestions.appendTo('body');

        const offset = $input.offset();
        $suggestions.css({
            position: 'absolute',
            top: offset.top + $input.outerHeight() + 2,  // +2 留点间隙
            left: offset.left,
            width: $input.outerWidth(),           // 关键：固定为 input 宽度
            minWidth: '300px',
            maxWidth: '300px',       // 取消可能的 max-width

        }).show();

        $.getJSON('/graph/api/search_agent', { q: q }, function (data) {
            $suggestions.empty();

            if (data.results.length === 0) {
                $suggestions.append('<li class="list-group-item text-muted">No results</li>');
                return;
            }

            data.results.forEach(r => {
                if (currentGraph.nodes.includes(r.id)) {
                    return; //已存在
                }

                const $item = $(`<li class="list-group-item list-group-item-action" style="cursor:pointer;">${r.display}</li>`);
                $item.on('click', function () {
                    $input.val(r.display);
                    if(r.type==='graph'){
                        agentsData = { ...agentsData, ...r.object.agents };
                        graphsById = { ...graphsById, ...r.object.graphs };
                        testSetsData={...testSetsData,...r.object.test_sets};
                    }else{
                        agentsData[r.id] = r.object.agent;  // 更新全局 agentsData
                        testSetsData[r.id]= r.object.test_sets
                    }

                    // 关键：选完后把 ul 移回原位（下次还能找到）
                    $suggestions.appendTo($input.parent()).hide();
                    $currentSuggestions = null;
                    $currentInput = null;
                    // ... 设置 input 显示、hidden 值等 ...
                    const oldRunnerId = $input.data('node-id');  // 旧的 runner id
                    const newRunnerId = r.id;                    // 新的 runner id

                    if (!oldRunnerId) {
                        currentGraph.nodes.push(newRunnerId);
                    } else {
                        // ========== 替换 currentGraph.nodes ==========
                        const nodeIndex = currentGraph.nodes.indexOf(oldRunnerId);
                        if (nodeIndex !== -1) {
                            currentGraph.nodes[nodeIndex] = newRunnerId;
                        }

                        // ========== 替换 currentGraph.edges 里所有 old 为 new ==========
                        let replacedCount = 0;
                        currentGraph.edges = currentGraph.edges.map(edge => {
                            let changed = false;
                            const newEdge = edge.map(part => {
                                if (part === oldRunnerId) {
                                    changed = true;
                                    return newRunnerId;
                                }
                                // 支持条件边 [[a,b], c]
                                if (Array.isArray(part)) {
                                    return part.map(p => {
                                        if (p === oldRunnerId) {
                                            changed = true;
                                            return newRunnerId;
                                        }
                                        return p;
                                    });
                                }
                                return part;
                            });

                            if (changed) replacedCount++;
                            return newEdge;
                        });


                    }

                    $input.data('node-id', r.id);
                    renderForm();
                    renderWorkflow(currentGraph);
                });
                $suggestions.append($item);
            });
        });
    });

    // 点击外部隐藏
    $(document).on('click', function(e) {
        if ($currentSuggestions && !$(e.target).closest('input, .suggestions').length) {
            $currentSuggestions.appendTo($currentInput.parent()).hide();
            $currentSuggestions = null;
            $currentInput = null;
        }
    });

    // ---------- Add Node 实时添加 ----------
    $('#addNodeBtn').on('click', function() {

        // 3. 创建 DOM：克隆第一个 node-item（如果有），或手动拼
        let $newItem = $(`
                <div class="node-item mb-3 d-flex align-items-center" data-index="">
                    <div class="flex-grow-1 position-relative me-2">
                        <input type="text"
                               class="form-control runner-search"
                               name="search"
                               placeholder="Search Agent or Workflow by name/ID..."
                               autocomplete="off"
                               value=""
                               data-node-id="">
                        <ul class="list-group position-absolute w-100 mt-1 shadow suggestions"
                            style="z-index: 9999; display: none; max-height: 300px; overflow-y: auto; width: 100%; background: white;">
                        </ul>
                    </div>
                    <button type="button"
                            class="btn btn-outline-danger btn-sm flex-shrink-0 remove-node"
                            data-index="">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `);

        // 4. 插入到列表（插到最后，或 addNodeBtn 前）
        $newItem.insertBefore($('.node-item-bottom'));
        // 或 $newItem.appendTo('#nodesList');
        // 6. 可选：自动聚焦新输入框
        $newItem.find('input.runner-search').focus();
    });


    // ---------- Add Edge 实时添加 ----------
    $('#addEdgeBtn').on('click', function() {

        let sourceOptions = '<option value="">-- Select Source --</option>';
        let targetOptions = '<option value="">-- Select Target --</option>';

        const allPossibleNodes = [...currentGraph.nodes.filter(n => n), 'START', 'END'];
        // 使用所有可能节点作为选项（包括 START 和 END）
        allPossibleNodes.forEach(n => {
            sourceOptions += `<option value="${n}" >${n}</option>`;
            targetOptions += `<option value="${n}">${n}</option>`;
        });
        const index=$('.edge-item').length;
        const $newItem = $(`
            <div class="edge-item row g-2 mb-2 align-items-center" data-index="${index}">
                <div class="col"><select class="form-select source-select" data-index="">${sourceOptions}</select></div>
                <div class="col-auto fs-5">→</div>
                <div class="col"><select class="form-select target-select" data-index="">${targetOptions}</select></div>
                <div class="col-auto"><button class="btn btn-outline-danger remove-edge" data-index="${index}"><i class="fas fa-trash"></i></button></div>
            </div>
        `);
        $newItem.appendTo('#edgesList');
    });

    // ---------- select 改变：实时更新 currentGraph.edges 和 paper ----------
    $('#edgesList').on('change', '.source-select, .target-select', function() {
        const $edgeItem = $(this).closest('.edge-item');
        const index = $edgeItem.data('index');
        const oldSource = $edgeItem.find('.source-select').data('index');
        const oldTarget = $edgeItem.find('.target-select').data('index');
        const source = $edgeItem.find('.source-select').val();
        const target = $edgeItem.find('.target-select').val();
        if (!source || !target) {
             return;
        }

        if (source === target) {
                alert('Source node can not be equal to Target node.');
                $edgeItem.find('.source-select').val(oldSource);
                $edgeItem.find('.target-select').val(oldTarget);
                return;
        }

        // ========== 查找是否已存在相同 (source(s), target) 的边 ==========
        const existingIndex = currentGraph.edges.findIndex(e => {
            let edgeSources = Array.isArray(e[0]) ? e[0] : [e[0]];
            let edgeTargets = Array.isArray(e[1])? e[1]: [e[1]];
            return edgeSources.includes(source) && edgeTargets.includes(target) ;
        });
        if (existingIndex !== -1) {
            alert(`Edge already exists: ${source} → ${target}`);
            $edgeItem.find('.source-select').val(oldSource);
            $edgeItem.find('.target-select').val(oldTarget);
            return;
        }


        if (oldSource && oldTarget) {
            //不同的target但是已存在边，更细腻
            currentGraph.edges[index] = [source, target];
        }else{
            //新的边
            currentGraph.edges.push([source, target]);
        }

        $edgeItem.find('.source-select').data('index',source);
        $edgeItem.find('.target-select').data('index',target);
        renderWorkflow(currentGraph);
    });

    $('#edgesList').on('click', '.remove-edge', function (e) {
        e.preventDefault();
        e.stopPropagation();

        if (!confirm('Are you sure you want to delete this edge?')) {
            return;
        }
        const edgeKey = $(this).data('index');  // 比如 "nodeA→nodeB"
        const from = $(this).closest('.edge-item').find('.source-select').val();
        const to = $(this).closest('.edge-item').find('.target-select').val();


        removeEdge(edgeKey, from, to);
        //从左侧抽屉 DOM 中移除对应的 edge-item
        const $edgeItem = $(`.edge-item[data-index="${edgeKey}"]`);
        if ($edgeItem.length) {
            $edgeItem.fadeOut(300, function () {
                $(this).remove();
            });
        }
    });

    $('#saveGraphBtn').on('click', saveGraph);


    // 初始状态：抽屉关闭
    toggleDrawer(false);


}



function initJointJS() {
    graph = new joint.dia.Graph();
    var $paperPanel = $('#paper_panel');

    paper = new joint.dia.Paper({
        el: $paperPanel[0],
        model: graph,
        width: $paperPanel.width(),
        height: 600,
        gridSize: 10,
        drawGrid: false,
        // ⭐ 关键配置：禁止所有节点拖拽
        interactive: function (cellView) {
            return {
                elementMove: false   // 禁止拖拽
            };
        }
    });

    // 渲染表单和预览
    if (current)
        renderForm();

    // 右键菜单事件
    $(paper.el).on('contextmenu', function (e) {
        e.preventDefault();
        var clientRect = paper.el.getBoundingClientRect();
        var x = e.clientX;
        var y = e.clientY;
        var targetElement = paper.findViewsFromPoint({ x: e.clientX - clientRect.left, y: e.clientY - clientRect.top })[0];
        if (!targetElement) {
            showContextMenu(x, y, [
                { label: 'Download graph as SVG', action: downloadGraphAsSVG }
            ]);
        }
    });

    /* ---------- 8. 节点点击事件 ---------- */
    paper.on('element:pointerdblclick', (elementView) => {
        const node = elementView.model;
        const id = node.id;
        //if (id === 'START' || id === 'END') return;          // 跳过
        const cfg = node.get('config') || {};
        const prompt = node.get('prompt') || {};

        if (id === 'START' || id === 'END') {
            const rows = [
                ['Inputs', (cfg.inputs || []).join(', ')],
                ['States', (cfg.state || []).join(', ')],
            ];
            // 2. 填充配置表格
            $('#configTable').html(
                rows.map(([key, value]) => `<tr><td>${key}</td><td>${value || ''}</td></tr>`).join('')
            );
        }else{
            // 填表
            const rows = [
                ['LLM URL', cfg.llm_url],
                ['Model', cfg.model],
                ['Inputs', (cfg.inputs || []).join(', ')],
                ['Outputs', `${cfg.outputs?.name || ''} (${cfg.outputs?.type || ''})`],
                ['Persistence', `${cfg.persistence?.file_path || ''} (${cfg.persistence?.file_type || ''})`]
            ];
            // 2. 填充配置表格
            $('#configTable').html(
                rows.map(([key, value]) => `<tr><td>${key}</td><td>${value || ''}</td></tr>`).join('')
            );

            // 3. 填充 Prompt 模板三个字段
            $('#descText').text(prompt.description || '');
            $('#sysText').text(prompt.system || '');
            $('#humanText').text(prompt.human || '');
            // 5. Relation Schema（仅当存在 head_type 或 tail_type 时显示）
            const schema = prompt.relation_schema || {};
            if (schema.head_type || schema.tail_type) {
                const schemaHtml = `
                    <div class="prompt-item">
                        <label>Relation Schema</label>
                        <pre>head_type: ${schema.head_type || '—'}\ntail_type: ${schema.tail_type || '—'}</pre>
                    </div>`;
                $('#schemaBox').html(schemaHtml);
            } else {
                $('#schemaBox').empty();
            }
        }
        // 4. 弹窗标题（优先取节点上显示的文字）
        $('#popupAgentName').text(node.attr('headerText/text') || id);



        // 6. 设置当前 runner ID（可能用于后续测试或保存）
        $('#agentId').val(id);

        // 7. 显示弹窗
        $('#agentPopup').removeClass('hidden');
    });

    paper.on('blank:pointerclick', () => {
        document.getElementById('agentPopup').classList.add('hidden');
    });
    paper.on('cell:mouseenter', cellView => {
        const cell = cellView.model;
        const subId = cell.get('subgraph');
        if (!subId) return;

        highlightSubgraph(subId, true);
    });

    paper.on('cell:mouseleave', cellView => {
        const cell = cellView.model;
        const subId = cell.get('subgraph');
        if (!subId) return;

        highlightSubgraph(subId, false);
    });
}


// ---------- 编辑模式：删除单个节点（核心函数） ----------
function removeNode(nodeId) {
    // 1. 从 currentGraph.nodes 中移除
    currentGraph.nodes = currentGraph.nodes.filter(n => n !== nodeId);

    // 2. 从 currentGraph.edges 中移除所有相关边（双向过滤）
    currentGraph.edges = currentGraph.edges.filter(([source, target]) =>
        source !== nodeId && target !== nodeId
    );
}


function renderForm() {

    // Edges 渲染（保持不变，只用 currentGraph.nodes 里的 id）
    const $edgesList = $('#edgesList').empty();
    const allPossibleNodes = [...currentGraph.nodes.filter(n => n), 'START', 'END'];

    // 处理边数据的辅助函数 - 展平为简单边数组

    function flattenEdges(edges) {
        const flattened = [];

        edges.forEach((edge, index) => {


            // 确保是数组且至少有两个元素
            if (!Array.isArray(edge) || edge.length < 2) {
                console.warn('Invalid edge format:', edge);
                return;
            }

            // 情况1：多源到单目标 [['from1', 'from2', ...], 'to']
            if (Array.isArray(edge[0]) && typeof edge[1] === 'string') {
                const sources = edge[0];
                const target = edge[1];


                // 遍历所有源节点
                sources.forEach(source => {
                    if (typeof source === 'string') {

                        flattened.push([source, target, index]);
                    }
                });
            }
            // 情况2：单源到多目标 ['from', ['to1', 'to2', ...]]
            else if (typeof edge[0] === 'string' && Array.isArray(edge[1])) {
                const source = edge[0];
                const targets = edge[1];

                // 遍历所有目标节点
                targets.forEach(target => {
                    if (typeof target === 'string') {

                        flattened.push([source, target, index]);
                    }
                });
            }
            // 情况3：简单边 ['from', 'to']
            else if (edge.length === 2 && typeof edge[0] === 'string' && typeof edge[1] === 'string') {

                flattened.push([edge[0], edge[1], index]);
            }
            // 其他格式
            else {
                console.warn('Unrecognized edge format:', edge);
            }
        });


        return flattened;
    }

    // 获取展平后的边数据
    let flattenedEdges = [];
    if (currentGraph && currentGraph.edges) {
        flattenedEdges = flattenEdges(currentGraph.edges);
    } else if (currentGraph.edges) {
        flattenedEdges = flattenEdges(currentGraph.edges);
    }

    // 渲染展平后的边
    flattenedEdges.forEach((edge, i) => {
        const [from, to, index] = edge;
        let sourceOptions = '<option value="">-- Select Source --</option>';
        let targetOptions = '<option value="">-- Select Target --</option>';

        // 使用所有可能节点作为选项（包括 START 和 END）
        allPossibleNodes.forEach(n => {
            sourceOptions += `<option value="${n}" ${n === from ? 'selected' : ''}>${n}</option>`;
            targetOptions += `<option value="${n}" ${n === to ? 'selected' : ''}>${n}</option>`;
        });

        const item = $(`
            <div class="edge-item row g-2 mb-2 align-items-center" data-index="${index}">
                <div class="col"><select class="form-select source-select" data-index="${from}">${sourceOptions}</select></div>
                <div class="col-auto fs-5">→</div>
                <div class="col"><select class="form-select target-select" data-index="${to}">${targetOptions}</select></div>
                <div class="col-auto"><button class="btn btn-outline-danger remove-edge" data-index="${index}"><i class="fas fa-trash"></i></button></div>
            </div>
        `);
        $edgesList.append(item);
    });
}

function removeEdge(edgeIndex, from, to) {
    if (typeof edgeIndex !== 'number' || edgeIndex < 0) {
        console.warn(`removeEdge: Invalid edge index ${edgeIndex}`);
        return false;
    }
    // 1. Resolve 高层到低层实际节点（如果 source 是 SUB，换成出口；target 是 SUB，换成入口）
    const sourceType = agentsData[from]?.type;
    if (sourceType === 'SUB') {
        const exitId = getSubgraphExit(from);
        if (exitId) {
            from = exitId;
        } else {
            console.warn(`Failed to resolve exit for subgraph source: ${from}`);
        }
    }
    const targetType = agentsData[to]?.type;
    if (targetType === 'SUB') {
        const entryId = getSubgraphEntry(to);
        if (entryId) {
            to = entryId;
        } else {
            console.warn(`Failed to resolve entry for subgraph target: ${to}`);
        }
    }

    const edgeKey = `${from}→${to} (index: ${edgeIndex})`;
    // 2. 从 currentGraph.edges 中直接 splice 删除（高效，且索引自动更新）
    currentGraph.edges.splice(edgeIndex, 1);

    // 3. 从 JointJS graph 中找到并删除对应的 link
    let removed = false;
    graph.getLinks().forEach(link => {
        const src = link.get('source')?.id;
        const tgt = link.get('target')?.id;
        if (src === from && tgt === to) {
            link.remove();
            removed = true;
        }
    });

    if (!removed) {
        console.warn(`Edge not found in graph: ${edgeKey}`);
    }
    return true;
}

function saveGraph() {
    const validNodes = currentGraph.nodes.filter(n => n);
    if (validNodes.length === 0) {
        alert('至少要有一个节点');
        return;
    }
    if (!validateGraph()) {

        return;
    }
    const data = {
        id: $('#graphId').val().trim(),
        description: $('#graphDescription').val().trim(),
        name: $('#graphName').val().trim(),
        nodes: validNodes,
        edges: currentGraph.edges
    };

    if (!data.id || !data.name) {
        alert('ID 和 Name 不能为空');
        return;
    }

    const url = '/graph/api/save';
    const method = 'POST';

    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function (response) {
            if (response.success) {
                alert('Workflow saved successfully!');
                window.location.href = `/graph/${response.id}/edit`;
            } else {
                alert('Save failed: ' + (response.error || 'Unknown error'));
            }
        },
        error: function (xhr) {
            const errMsg = xhr.responseJSON?.error || xhr.statusText || 'Network error';
            alert('Save failed: ' + errMsg);
        }
    });
}

function validateGraph() {
    function validateWorkflow(nodes, edges, workflowName = 'Main Workflow') {
        if (!Array.isArray(nodes) || nodes.length === 0) {
            alert(`${workflowName} must have at least one node.`);
            return false;
        }

        const outgoing = {};
        nodes.forEach(n => outgoing[n] = new Set());

        // 解析边并统计出边
        for (const edge of edges) {
            let sources = [];
            let target;

            if (Array.isArray(edge[0])) {
                sources = edge[0];
                target = edge[1];
            } else {
                sources = [edge[0]];
                target = edge[1];
            }

            // target 允许 END
            if (target !== 'END' && !nodes.includes(target)) {
                alert(`Edge target "${target}" does not exist in ${workflowName}.`);
                return false;
            }

            for (const src of sources) {
                if (src !== 'START' && !nodes.includes(src)) {
                    alert(`Edge source "${src}" does not exist in ${workflowName}.`);
                    return false;
                }
                if (src !== 'START') {
                    outgoing[src] = outgoing[src] || new Set();
                    outgoing[src].add(target);
                }
            }
        }

        // ========== 核心检查：除了隐式终点节点，其他所有节点必须有出边 ==========
        for (const node of nodes) {
            if (outgoing[node].size === 0) {
                // 这个节点无出边 → 它是隐式终点 → 允许
                alert(`Node "${node}" has no outgoing edge, treated as terminal (connects to implicit END).`);
                return false

            } else {
                // 有出边 → 正常中间节点 → 必须有后续 → 通过
            }
        }

        // ========== 可选温和检查：是否有起点（无入边的节点） ==========
        // 计算入度
        const incoming = {};
        nodes.forEach(n => incoming[n] = new Set());
        edges.forEach(edge => {
            let target = Array.isArray(edge[0]) ? edge[1] : edge[1];
            if (target !== 'END' && nodes.includes(target)) {
                incoming[target].add('someone');
            }
        });

        for (const node of nodes) {
            if (incoming[node].size === 0) {
                alert(`No explicit start node in ${node}.`);
                return false;
            } else {

            }
        }

        // ========== 递归校验子图 ==========
        for (const node of nodes) {
            const agent = agentsData[node];
            if (agent && agent.type === 'SUB') {
                const subGraph = graphsById[node];
                if (!subGraph || !Array.isArray(subGraph.nodes) || !Array.isArray(subGraph.edges)) {
                    alert(`Subgraph "${node}" configuration is missing or invalid.`);
                    return false;
                }
                if (!validateWorkflow(subGraph.nodes, subGraph.edges, `Subgraph "${node}"`)) {
                    return false;
                }
            }
        }

        return true;
    }

    // 主流程准备
    const validNodes = currentGraph.nodes.filter(n => n && n.trim() !== '');
    const validEdges = currentGraph.edges.filter(e => {
        if (!Array.isArray(e)) return false;
        let source = Array.isArray(e[0]) ? e[0][0] : e[0];
        let target = e[1];
        return (source && target) &&
            (validNodes.includes(source) || source === 'START') &&
            (validNodes.includes(target) || target === 'END');
    });

    if (validNodes.length === 0) {
        alert('Workflow must have at least one real node.');
        return false;
    }

    return validateWorkflow(validNodes, validEdges, 'Main Workflow');
}
// 创建节点
function createNode(id) {
    const isStartEnd = id === 'START' || id === 'END';
    const type = agentsData[id]?.type;
    const style = isStartEnd ? nodeStyles.startEnd : nodeStyles[type];

    /* 找不到数据 && 不是 START/END → 空节点 */
    if (!isStartEnd && !style) {
        return new joint.shapes.standard.Rectangle({
            id: id,                       // 关键：保持原 id
            position: { x: 0, y: 0 },
            size: { width: 100, height: 50 },
            attrs: {
                body: {
                    fill: 'transparent',
                    stroke: '#ff0000',   // 红色虚线提示“空”
                    strokeDasharray: '3,3',
                    strokeWidth: 1
                },
                label: { text: id, fontSize: 10, fill: '#999' }
            }
        });
    }

    const label = agentsData[id]?.name || id;
    /* 第二行：model 名（仅 Normal 节点显示） */

    let bodyText = '';
    const bodyTextBuilders = {
        PGM: a => `inputs: ${a.inputs || 'N/A'}\noutputs: ${a.outputs?.name || 'N/A'}`,
        LLM: a => `model: ${a.model || 'N/A'}\ninputs: ${a.inputs || 'N/A'}\noutputs: ${a.outputs?.name || 'N/A'}`,
        default: a => ''
    };

    bodyText = (bodyTextBuilders[type] || bodyTextBuilders.default)(agentsData[id]);
    if (isStartEnd) {
         return new joint.shapes.standard.Rectangle({
            id,
            size: { width: 100, height: 50 },
            attrs: {
                body: {
                    fill: '#ffffff',
                    stroke: style.stroke,
                    strokeWidth: 2,
                    rx: 1, ry: 1
                },
                label: {
                    text: label,
                    fill: '#333333',
                    fontSize: 12,
                    fontWeight: 'normal',
                    textWrap: { width: 124, height: 68, ellipsis: true }
                }
            },
            config: { inputs: graphsById.inputs, state: graphsById.state }
        });
    }
    const headeredRectangle = new joint.shapes.standard.HeaderedRectangle();
        headeredRectangle.resize(150, 100);
        //headeredRectangle.position(x, y);
        headeredRectangle.attr('root/title', id);
        headeredRectangle.attr({
            headerText: {
                text: label,
                fontSize: 12,
                fontWeight: 'bold',
                textWrap: {
                    width: 124,
                    height: 34,
                    ellipsis: true
                },
            },
            header: {
                fill: '#ffffff',          // 白底
                stroke: style.stroke,     // 彩色边框
                strokeWidth: 2,

            },
            bodyText: {
                text: bodyText,
                fontSize: 12,
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
                fill: '#ffffff',          // 白底
                stroke: style.stroke,     // 彩色边框
                strokeWidth: 2,
                rx: 1,
                ry: 1,
                height: 100 // 调整 body 的高度
            }
        });
        /* 1. 取数据 */
        const cfg = agentsData[id] || {};          // 第一段 JSON
        const prompt = cfg['prompt_template'] || {};
        headeredRectangle.set({
            id: id,
            //workflow: workflow,
            config: cfg,        // 第一段
            prompt: prompt      // 第二段
        });

        return headeredRectangle;
}

function expandSubgraph(wf) {
    const nodes = [];
    const edges = [];
    subgraphRanges = {};

    const isSub = id => agentsData[id]?.type === 'SUB';

    function ensureRange(id) {
        if (!subgraphRanges[id]) {
            subgraphRanges[id] = { nodes: [], subgraphs: [] };
        }
    }

    function getEntries(subId) {
        const sub = graphsById[subId];
        if (!sub) return [];
        return sub.edges
            .filter(([s]) => s === 'START')
            .map(([_, t]) => t)
            .flatMap(t => isSub(t) ? getEntries(t) : [t]);
    }

    function getExits(subId) {
        const sub = graphsById[subId];
        if (!sub) return [];
        return sub.edges
            .filter(([_, t]) => t === 'END')
            .map(([s]) => s)
            .flatMap(s => isSub(s) ? getExits(s) : [s]);
    }

    function expandSubRecursive(subId) {
        const sub = graphsById[subId];
        if (!sub) return;

        ensureRange(subId);

        // -------- nodes --------
        sub.nodes.forEach(n => {
            if (n === 'START' || n === 'END') return;

            if (isSub(n)) {
                ensureRange(n);
                subgraphRanges[subId].subgraphs.push(n);
                expandSubRecursive(n);
            } else {
                nodes.push(n);
                subgraphRanges[subId].nodes.push(n);
            }
        });

        // -------- edges（关键修正点）--------
        sub.edges.forEach(([s, t]) => {
            if (s === 'START' || t === 'END') return;

            const sIsSub = isSub(s);
            const tIsSub = isSub(t);

            if (!sIsSub && !tIsSub) {
                edges.push([s, t]);
            }
            else if (!sIsSub && tIsSub) {
                getEntries(t).forEach(et => edges.push([s, et]));
            }
            else if (sIsSub && !tIsSub) {
                getExits(s).forEach(es => edges.push([es, t]));
            }
            else {
                getExits(s).forEach(es =>
                    getEntries(t).forEach(et =>
                        edges.push([es, et])
                    )
                );
            }
        });
    }

    // ---------- 顶层 ----------
    wf.nodes.forEach(id => {
        if (isSub(id)) {
            expandSubRecursive(id);
        } else {
            nodes.push(id);
        }
    });

    // ---------- 父流程 edges ----------
    wf.edges.forEach(([src, tgt]) => {
        const srcArr = Array.isArray(src) ? src : [src];
        const tgtArr = Array.isArray(tgt) ? tgt : [tgt];

        srcArr.forEach(s => tgtArr.forEach(t => {
            const sIsSub = isSub(s);
            const tIsSub = isSub(t);

            if (!sIsSub && !tIsSub) {
                edges.push([s, t]);
            }
            else if (!sIsSub && tIsSub) {
                getEntries(t).forEach(et => edges.push([s, et]));
            }
            else if (sIsSub && !tIsSub) {
                getExits(s).forEach(es => edges.push([es, t]));
            }
            else {
                getExits(s).forEach(es =>
                    getEntries(t).forEach(et =>
                        edges.push([es, et])
                    )
                );
            }
        }));
    });

    const uniqueNodes = Array.from(new Set(nodes));
    const nodeSet = new Set(uniqueNodes.concat(['START', 'END']));

    const safeEdges = edges.filter(([s, t]) => {
        if (!nodeSet.has(s) || !nodeSet.has(t)) {
            console.warn('❌ drop invalid edge:', s, '→', t);
            return false;
        }
        return true;
    });

    return { nodes: uniqueNodes, edges: safeEdges };
}


function drawSubgraphContainers() {

    // 子 → 父（深度大的先画）
    const ordered = Object.keys(subgraphRanges)
        .sort((a, b) => getSubgraphDepth(b) - getSubgraphDepth(a));

    const containerBBoxes = {}; // ⭐ 记录每个 subgraph 的 bbox

    ordered.forEach(subId => {
        const info = subgraphRanges[subId];

        let elements = [];

        // 1️⃣ 自己的真实节点
        (info.nodes || []).forEach(id => {
            const el = graph.getCell(id);
            if (el) elements.push(el.getBBox());
        });

        // 2️⃣ 子 subgraph 的 bbox（不是 cell）
        (info.subgraphs || []).forEach(childId => {
            const childBBox = containerBBoxes[childId];
            if (childBBox) elements.push(childBBox);
        });

        if (!elements.length) return;

        // 3️⃣ 合并 bbox
        let bbox = elements[0];
        elements.slice(1).forEach(b => bbox = bbox.union(b));

        const padding = 40; // ⭐ 建议稍微大一点

        const rect = new joint.shapes.standard.Rectangle();
        rect.position(bbox.x - padding, bbox.y - padding);
        rect.resize(
            bbox.width + padding * 2,
            bbox.height + padding * 2
        );

        rect.attr({
            body: {
                fill: 'rgba(118,75,162,0.06)',
                stroke: '#764ba2',
                strokeDasharray: '5 5',
                rx: 12,
                ry: 12
            },
            label: {
                text: agentsData[subId]?.name || subId,
                fill: '#764ba2',
                fontSize: 12,
                fontWeight: 'bold',
                refX: 10,
                refY: 10,
                textAnchor: 'start',
                textVerticalAnchor: 'top'
            }
        });

        rect.set({
            z: -10,
            subgraph: subId,
            interactive: false
        });

        graph.addCell(rect);

        // ⭐ 记录 bbox，给父 subgraph 用
        containerBBoxes[subId] = rect.getBBox();
    });
}


// 创建连接线
function createLink(sourceId, targetId) {
    const link = new joint.shapes.standard.Link();
    link.source({ id: sourceId });
    link.target({ id: targetId });
    link.attr({
        line: {
            stroke: '#666',
            strokeWidth: 2,
            targetMarker: {
                type: 'path',
                d: 'M 10 -5 0 0 10 5 z'
            }
        }
    });
    // ---------- 线型 ----------
    // 'normal': 直线, 'smooth': 平滑曲线, 'rounded': 圆角折线, 'orthogonal': 折线
    link.connector('smooth', { radius: 20 });
    return link;
}


// 渲染工作流
function renderWorkflow(wf) {

    // ---------- 0. 清空 ----------
    graph.clear();
    subgraphRanges = {};



    // ---------- 1. 展开 workflow（递归 subgraph） ----------
    const { nodes, edges } = expandSubgraph(wf);

    // ⚠️ START / END 必须显式存在
    const allNodes = ['START', ...nodes, 'END'];

    // ---------- 2. 创建节点 ----------
    const nodeCells = allNodes.map(id => createNode(id));

    // ---------- 3. 创建边 ----------
    const linkCells = [];
    edges.forEach(([s, t]) => {
        if (graph.getCell(s) || allNodes.includes(s)) {
            if (graph.getCell(t) || allNodes.includes(t)) {
                linkCells.push(createLink(s, t));
            }
        }
    });

    // ---------- 4. 一次性加入 graph（顺序很重要） ----------
    graph.resetCells([
        ...nodeCells,
        ...linkCells
    ]);

    // ---------- 5. Dagre 布局（只作用于真实节点） ----------
    joint.layout.DirectedGraph.dagre = dagre;
    joint.layout.DirectedGraph.layout(graph, {
        rankDir: 'LR',
        nodeSep: 60,
        rankSep: 120,
        edgeSep: 40,
        marginX: 30,
        marginY: 30
    });

    // ---------- 6. 画 subgraph 容器（嵌套） ----------
    drawSubgraphContainers();

    // ---------- 7. 自适应视图 ----------
    fitToContent();
}


function fitToContent() {
    const bbox = graph.getBBox();
    const pw = paper.el.clientWidth;
    const ph = paper.el.clientHeight;
    if (bbox) {
        const sc = Math.min(pw / bbox.width, ph / bbox.height) * 0.9;
        paper.scale(sc, sc);
        paper.translate(
            -bbox.x * sc + (pw - bbox.width * sc) / 2,
            -bbox.y * sc + (ph - bbox.height * sc) / 2
        );
    }
}

function getSubgraphDepth(id, depth = 0) {
    for (const [k, v] of Object.entries(subgraphRanges)) {
        if (v.subgraphs?.includes(id)) {
            return getSubgraphDepth(k, depth + 1);
        }
    }
    return depth;
}

function getSubgraphElements(subId) {
    const info = subgraphRanges[subId];
    if (!info) return [];

    let elements = [];

    // 自己的节点
    (info.nodes || []).forEach(id => {
        const el = graph.getCell(id);
        if (el) elements.push(el);
    });

    // 子 subgraph（递归）
    (info.subgraphs || []).forEach(childId => {
        const childRect = graph.getCells().find(c =>
            c.get('subgraph') === childId
        );
        if (childRect) elements.push(childRect);

        elements = elements.concat(getSubgraphElements(childId));
    });

    return elements;
}

function highlightSubgraph(subId, on) {
    const rect = graph.getCells().find(c => c.get('subgraph') === subId);
    if (!rect) return;

    // subgraph 容器
    rect.attr('body', {
        stroke: on ? '#5b3cc4' : '#764ba2',
        strokeWidth: on ? 3 : 1.5,
        fill: on
            ? 'rgba(118,75,162,0.12)'
            : 'rgba(118,75,162,0.06)'
    });

    // 内部元素
    getSubgraphElements(subId).forEach(el => {
        if (el.isElement()) {
            el.attr('body/stroke', on ? '#5b3cc4' : '#333');
            el.attr('body/strokeWidth', on ? 2 : 1);
        }
    });
}

// ---------- 高亮子流程 ----------
function highlightSubgraph(subId) {
    const info = subgraphRanges[subId];
    if (!info) return;
    const allCells = [...(info.nodes || []), ...(info.subgraphs || [])]
        .map(id => graph.getCell(id))
        .filter(Boolean);
    allCells.forEach(c => c.attr('body/stroke', '#ff5722')); // 高亮橙色
    setTimeout(() => {
        allCells.forEach(c => c.attr('body/stroke', agentsData[c.id]?.type === 'SUB' ? '#764ba2' : '#28a745'));
    }, 2000);
}


// ---------- 下载 SVG ----------
function downloadGraphAsSVG() {
    const svgElement = paper.svg;
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'workflow.svg';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    URL.revokeObjectURL(url);
}

// 获取子图的出口节点 ID（递归找 deepest 最后一个节点）
function getSubgraphExit(subId) {
    const info = subgraphRanges[subId];
    if (!info) {
        console.warn(`Subgraph not found: ${subId}`);
        return null;
    }

    // 如果有子子图，递归到最深层的最后一个子图出口
    if (info.subgraphs && info.subgraphs.length) {
        const lastSub = info.subgraphs[info.subgraphs.length - 1];
        return getSubgraphExit(lastSub);
    }

    // 无子子图，返回自己的 nodes 最后一个
    if (info.nodes && info.nodes.length) {
        return info.nodes[info.nodes.length - 1];
    }

    return null;
}

// 获取子图的入口节点 ID（递归找 deepest 第一个节点）
function getSubgraphEntry(subId) {
    const info = subgraphRanges[subId];
    if (!info) {
        console.warn(`Subgraph not found: ${subId}`);
        return null;
    }

    // 如果有子子图，递归到最深层的第一个子图入口
    if (info.subgraphs && info.subgraphs.length) {
        const firstSub = info.subgraphs[0];
        return getSubgraphEntry(firstSub);
    }

    // 无子子图，返回自己的 nodes 第一个
    if (info.nodes && info.nodes.length) {
        return info.nodes[0];
    }

    return null;
}