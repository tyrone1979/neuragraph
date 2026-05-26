// NeuraGraph Visual Editor — Dify-style
var WF_COMPLETE_MSG = 'Workflow completed.';
let graph, paper, selectedCell = null, historyStack = [], redoStack = [];
let subgraphRanges = {}, nodeCounter = 0, currentGraph = null, graphBindings = {};

function getGraphFlowNodes(wf) {
    wf = wf || currentGraph || {};
    return wf.flowNodes || {};
}

function getGraphBindings(wf) {
    wf = wf || currentGraph || {};
    return wf.bindings || {};
}

function _applyFlowNodeMeta(nid, f) {
    if (!agentsData[nid]) agentsData[nid] = { id: nid };
    agentsData[nid].id = nid;
    agentsData[nid].name = f.name || agentsData[nid].name || nid;
    agentsData[nid].flowKind = f.kind;
    if (f.kind === 'loop') {
        agentsData[nid].loopConfig = f.loopConfig || {};
        if (!agentsData[nid].type || agentsData[nid].type === 'loop') agentsData[nid].type = 'PGM';
    } else if (f.kind === 'branch') {
        agentsData[nid].conditions = f.conditions || [];
        if (!agentsData[nid].type || agentsData[nid].type === 'branch') agentsData[nid].type = 'PGM';
    }
}

function mergeFlowNodesFromGraph(wf) {
    var fn = getGraphFlowNodes(wf);
    Object.keys(fn).forEach(function(nid) { _applyFlowNodeMeta(nid, fn[nid]); });
    if (graphsById) {
        Object.keys(graphsById).forEach(function(gid) {
            var gfn = (graphsById[gid] && graphsById[gid].flowNodes) || {};
            Object.keys(gfn).forEach(function(nid) { _applyFlowNodeMeta(nid, gfn[nid]); });
        });
    }
    graphBindings = Object.assign({}, getGraphBindings(wf));
    if (graphsById) {
        Object.keys(graphsById).forEach(function(gid) {
            var gb = (graphsById[gid] && graphsById[gid].bindings) || {};
            graphBindings = Object.assign(graphBindings, gb);
        });
    }
}

function getNodeFlowKind(nid, wf) {
    var fn = getGraphFlowNodes(wf)[nid];
    return fn ? fn.kind : null;
}
let availableLLMs = [];

const nodeStyles = {
    startEnd: { stroke: '#17a2b8' }, PGM: { stroke: '#28a745' },
    LLM: { stroke: '#4b6cb7' }, SUB: { stroke: '#764ba2' },
    branch: { stroke: '#f59e0b' }, loop: { stroke: '#3b82f6' }, tool: { stroke: '#ec4899' }
};
const typeIcons = { PGM:'fa-cog',LLM:'fa-robot',SUB:'fa-project-diagram',branch:'fa-code-branch',loop:'fa-redo',tool:'fa-wrench',flow:'fa-arrow-right' };
const typeLabels = { PGM:'Code', LLM:'LLM', SUB:'Subgraph', branch:'IF/ELSE', loop:'Loop', tool:'Tool', flow:'Flow' };
const typeIconLetters = { PGM:'C', LLM:'L', SUB:'S', branch:'?', loop:'↻', tool:'T', flow:'▶' };

const WF_NODE_WIDTH = 268;
const ZOOM_MIN = 0.2;
const ZOOM_MAX = 3;
const ZOOM_BTN_STEP = 0.2;
const ZOOM_WHEEL_STEP = 0.08;
const WF_HEADER_H = 40;
const WF_ROW_H = 24;
const WF_SECTION_LABEL_H = 18;
const WF_BODY_PAD = 12;

const WF_PORT_GROUPS = {
    in: {
        position: { name: 'left' },
        attrs: {
            circle: {
                r: 6, magnet: true, fill: '#fff', stroke: '#3b82f6', strokeWidth: 2,
                cursor: 'crosshair'
            }
        },
        markup: [{ tagName: 'circle', selector: 'circle' }]
    },
    out: {
        position: { name: 'right' },
        attrs: {
            circle: {
                r: 6, magnet: true, fill: '#fff', stroke: '#10b981', strokeWidth: 2,
                cursor: 'crosshair'
            }
        },
        markup: [{ tagName: 'circle', selector: 'circle' }]
    }
};

function portYPercent(yPx, height) {
    var pct = (yPx / Math.max(height, 1)) * 100;
    return Math.max(10, Math.min(90, pct)) + '%';
}

function sanitizePortId(label) {
    return String(label || 'out').replace(/[^a-zA-Z0-9_]/g, '_').replace(/^_+/, '') || 'out';
}

function resolvePortEndpoint(cell, side, preferredPortId) {
    if (!cell || !cell.getPorts) return { id: cell ? cell.id : '' };
    var ports = cell.getPorts() || [];
    if (cell.id === 'START' && side === 'out') return { id: 'START', port: 'out_trigger' };
    if (cell.id === 'END' && side === 'in') return { id: 'END', port: 'in_input' };
    var group = side === 'out' ? 'out' : 'in';
    var matched = ports.filter(function(p) { return p.group === group; });
    if (preferredPortId) {
        var hit = matched.find(function(p) { return p.id === preferredPortId; });
        if (hit) return { id: cell.id, port: hit.id };
    }
    if (matched.length) return { id: cell.id, port: matched[0].id };
    return { id: cell.id };
}

function escHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function truncateText(s, max) {
    s = String(s == null ? '' : s);
    return s.length > max ? s.slice(0, max - 1) + '\u2026' : s;
}

function normalizeInputs(agent) {
    var raw = (agent && agent.inputs) || [];
    if (Array.isArray(raw)) return raw.map(String);
    if (typeof raw === 'string') return raw.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
    return [];
}

function getNodeStroke(type, isSE) {
    if (isSE) return nodeStyles.startEnd.stroke;
    return (nodeStyles[type] || nodeStyles.LLM).stroke;
}

function defineWorkflowNodeShape() {
    if (joint.shapes.neuragraph && joint.shapes.neuragraph.WorkflowNode) return;
    var NS = 'http://www.w3.org/1999/xhtml';
    joint.shapes.neuragraph = joint.shapes.neuragraph || {};
    joint.shapes.neuragraph.WorkflowNode = joint.dia.Element.define('neuragraph.WorkflowNode', {
        attrs: {
            root: { magnet: false },
            body: {
                refWidth: '100%', refHeight: '100%',
                fill: 'transparent', stroke: '#e5e7eb', strokeWidth: 1.5,
                rx: 12, ry: 12
            },
            fo: { refWidth: '100%', refHeight: '100%', x: 0, y: 0 },
            content: {}
        },
        ports: { groups: WF_PORT_GROUPS }
    }, {
        markup: [
            { tagName: 'rect', selector: 'body' },
            {
                tagName: 'foreignObject',
                selector: 'fo',
                attributes: { overflow: 'hidden' },
                children: [{ tagName: 'div', selector: 'content', namespaceURI: NS }]
            }
        ]
    });
}

function buildNodeLayout(id, agent) {
    var isSE = id === 'START' || id === 'END';
    var type = (agent && agent.type) || 'LLM';
    var displayType = (agent && agent.flowKind) || type;
    var stroke = getNodeStroke(displayType, isSE);
    var name = truncateText((agent && agent.name) || id, 28);
    var inputs = normalizeInputs(agent);
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : '';
    var outType = (agent && agent.outputs && agent.outputs.type) ? String(agent.outputs.type) : '';
    var model = (agent && agent.model) ? truncateText(agent.model, 32) : '';
    var tools = (agent && agent.tools) || [];

    var metaLines = 0;
    if (type === 'LLM' && model) metaLines++;
    if (tools.length) metaLines++;
    var showIdRow = agent && agent.id && agent.name && agent.id !== agent.name;

    var inRowCount = Math.max(inputs.length, 1);
    var branchConds = (displayType === 'branch')
        ? ((agent && agent.conditions) || [{ label: 'True' }, { label: 'False' }])
        : [];
    var outRowCount = (displayType === 'branch') ? Math.max(branchConds.length, 1) : 1;
    var bodyH = WF_BODY_PAD
        + (metaLines ? metaLines * 20 + 4 : 0)
        + (showIdRow ? 14 : 0)
        + WF_SECTION_LABEL_H + inRowCount * WF_ROW_H
        + WF_SECTION_LABEL_H + outRowCount * WF_ROW_H
        + WF_BODY_PAD;
    var height = WF_HEADER_H + bodyH;
    var width = WF_NODE_WIDTH;

    var portItems = [];
    var yBase = WF_HEADER_H + WF_BODY_PAD;
    if (metaLines) yBase += metaLines * 20 + 4;
    if (showIdRow) yBase += 14;
    yBase += WF_SECTION_LABEL_H;

    inputs.forEach(function(inp, i) {
        var yIn = yBase + i * WF_ROW_H + WF_ROW_H / 2;
        portItems.push({
            id: 'in_' + inp,
            group: 'in',
            args: { y: portYPercent(yIn, height) }
        });
    });
    if (!inputs.length) {
        portItems.push({
            id: 'in_default', group: 'in',
            args: { y: portYPercent(yBase + WF_ROW_H / 2, height) }
        });
    }

    var yOutSection = yBase + inRowCount * WF_ROW_H + WF_SECTION_LABEL_H;
    if (displayType === 'branch') {
        branchConds.forEach(function(c, i) {
            var yBr = yOutSection + i * WF_ROW_H + WF_ROW_H / 2;
            portItems.push({
                id: 'out_' + sanitizePortId(c.label),
                group: 'out',
                args: { y: portYPercent(yBr, height) }
            });
        });
        if (!branchConds.length) {
            portItems.push({
                id: 'out_default', group: 'out',
                args: { y: portYPercent(yOutSection + WF_ROW_H / 2, height) }
            });
        }
    } else {
        var yOut = yOutSection + WF_ROW_H / 2;
        var outId = outName ? ('out_' + outName) : 'out_default';
        portItems.push({
            id: outId, group: 'out',
            args: { y: portYPercent(yOut, height) }
        });
    }

    var iconLetter = typeIconLetters[displayType] || typeIconLetters[type] || type.charAt(0) || '?';
    var typeLabel = typeLabels[displayType] || typeLabels[type] || type;
    var html = '<div class="wf-node" xmlns="' + escHtml('http://www.w3.org/1999/xhtml') + '">';
    html += '<div class="wf-node-header" style="background:' + escHtml(stroke) + '">';
    html += '<span class="wf-node-icon">' + escHtml(iconLetter) + '</span>';
    html += '<span class="wf-node-title" title="' + escHtml((agent && agent.name) || id) + '">' + escHtml(name) + '</span>';
    html += '<span class="wf-node-type" title="' + escHtml(type) + '">' + escHtml(typeLabel) + '</span>';
    html += '</div><div class="wf-node-body">';

    if (showIdRow) {
        html += '<div class="wf-node-id" title="' + escHtml(agent.id) + '">' + escHtml(truncateText(agent.id, 36)) + '</div>';
    }
    if (type === 'LLM' && model) {
        html += '<div class="wf-node-meta" title="' + escHtml(agent.model) + '">Model: ' + escHtml(model) + '</div>';
    } else if (type === 'PGM') {
        html += '<div class="wf-node-meta">Rule-based / Python</div>';
    } else if (type === 'SUB') {
        html += '<div class="wf-node-meta">Iterates over list input</div>';
    } else if (displayType === 'branch') {
        html += '<div class="wf-node-meta">Conditional routing (graph flow)</div>';
    } else if (displayType === 'loop') {
        html += '<div class="wf-node-meta">Loop container (graph flow)</div>';
    }
    if (tools.length) {
        html += '<div class="wf-node-meta" title="' + escHtml(tools.join(', ')) + '">Tools: ' + escHtml(truncateText(tools.join(', '), 40)) + '</div>';
    }

    html += '<div class="wf-io-block"><div class="wf-io-label">INPUT</div>';
    if (inputs.length) {
        inputs.forEach(function(inp) {
            html += '<div class="wf-io-row"><span class="wf-io-dot wf-io-dot--in"></span>';
            html += '<span class="wf-io-name" title="' + escHtml(inp) + '">' + escHtml(truncateText(inp, 22)) + '</span></div>';
        });
    } else {
        html += '<div class="wf-io-empty">—</div>';
    }
    html += '</div>';

    html += '<div class="wf-io-block"><div class="wf-io-label">OUTPUT</div>';
    if (displayType === 'branch' && branchConds.length) {
        branchConds.forEach(function(c) {
            html += '<div class="wf-io-row"><span class="wf-io-dot wf-io-dot--out"></span>';
            html += '<span class="wf-io-name" title="' + escHtml(c.label) + '">' + escHtml(truncateText(c.label, 20)) + '</span>';
            html += '<span class="wf-io-type">out</span></div>';
        });
    } else if (outName) {
        html += '<div class="wf-io-row"><span class="wf-io-dot wf-io-dot--out"></span>';
        html += '<span class="wf-io-name" title="' + escHtml(outName) + '">' + escHtml(truncateText(outName, 20)) + '</span>';
        if (outType) html += '<span class="wf-io-type">' + escHtml(truncateText(outType, 8)) + '</span>';
        html += '</div>';
    } else {
        html += '<div class="wf-io-empty">—</div>';
    }
    html += '</div></div></div>';

    return {
        width: width, height: height, html: html, stroke: stroke,
        portItems: portItems,
        config: {
            id: id, name: (agent && agent.name) || id,
            inputs: inputs,
            outputs: agent ? agent.outputs : null,
            type: type, flowKind: (agent && agent.flowKind) || '',
            model: model,
            tools: tools,
            persistence: (agent && agent.persistence) || null,
            loopConfig: (agent && agent.loopConfig) || {},
            conditions: (agent && agent.conditions) || []
        }
    };
}

function applyNodeVisual(el, layout, selected) {
    if (!el || !layout) return;
    el.resize(layout.width, layout.height);
    el.attr({
        fo: { width: layout.width, height: layout.height },
        body: {
            stroke: selected ? '#ff5722' : layout.stroke,
            strokeWidth: selected ? 3 : 1.5
        },
        content: { html: layout.html }
    });
    el.set('ports', { groups: WF_PORT_GROUPS, items: layout.portItems });
}

function refreshNodeVisual(agentId) {
    var el = graph.getCell(agentId);
    if (!el || el.get('subgraph')) return;
    var agent = agentsData[agentId] || el.get('config');
    if (!agent) return;
    var layout = buildNodeLayout(agentId, agent);
    var selected = selectedCell && selectedCell.id === agentId;
    applyNodeVisual(el, layout, selected);
    el.set('config', layout.config);
    updateSubgraphContainerPositions();
}

// ─── Init ───────────────────────────────────────────
$(document).ready(function() {
    initJointJS();
    initUI();
    initToolbarDrag();
    $('#zoomIn').on('click', function() { zoomClamped(ZOOM_BTN_STEP); });
    $('#zoomOut').on('click', function() { zoomClamped(-ZOOM_BTN_STEP); });
    $('#fitToContent').on('click', fitToContent);
    $('#resetView').on('click', resetView);
    $('#btnDelete').on('click', deleteSelected);
    $('#btnUndo').on('click', undo);
    $('#btnRedo').on('click', redo);
    $('#saveGraphBtn').on('click', saveGraph);
    $('#testWorkflow').on('click', openTestModal);
    $('#runTestBtn').on('click', runTest);
    $('#componentSearch').on('input', function() {
        const q = $(this).val().toLowerCase();
        $('.component-item').each(function() { $(this).toggle($(this).text().toLowerCase().includes(q)); });
    });
    loadComponents().then(function() {
        if (current && graphsById && graphsById[current]) {
            currentGraph = graphsById[current];
            renderWorkflow(currentGraph);
        } else { createDefaultWorkflow(); }
    });
    $('#propName').on('input change blur', function() {
        if (!selectedCell || !selectedCell.isElement()) return;
        var cfg = selectedCell.get('config');
        if (!cfg || cfg.type === 'flow') return;
        cfg.name = $(this).val();
        selectedCell.set('config', cfg);
        if (agentsData[cfg.id]) agentsData[cfg.id].name = cfg.name;
        refreshNodeVisual(cfg.id);
    });
});

// ─── Toolbar drag ───────────────────────────────────
function initToolbarDrag() {
    const tb = document.getElementById('toolbar'), cv = document.getElementById('canvasContainer');
    if (!tb || !cv) return;
    let drag = false, sx, sy, ix, iy;
    tb.addEventListener('mousedown', function(e) {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
        drag = true; sx = e.clientX; sy = e.clientY;
        const r = tb.getBoundingClientRect(), cr = cv.getBoundingClientRect();
        ix = r.left - cr.left; iy = r.top - cr.top; tb.style.cursor = 'grabbing';
    });
    document.addEventListener('mousemove', function(e) {
        if (!drag) return;
        const cr = cv.getBoundingClientRect(), tr = tb.getBoundingClientRect();
        let nx = ix + (e.clientX - sx), ny = iy + (e.clientY - sy);
        nx = Math.max(0, Math.min(nx, cr.width - tr.width));
        ny = Math.max(0, Math.min(ny, cr.height - tr.height));
        tb.style.left = nx + 'px'; tb.style.top = ny + 'px'; tb.style.transform = 'none';
    });
    document.addEventListener('mouseup', function() { if (drag) { drag = false; tb.style.cursor = 'move'; } });
}

// ─── Background color ───────────────────────────────
function initUI() {
    const cp = document.getElementById('bgColorPicker');
    if (cp) cp.addEventListener('input', function(e) {
        document.getElementById('canvasContainer').style.backgroundColor = e.target.value;
        if (paper) { paper.options.background = { color: e.target.value }; paper.render(); }
    });
    const cb = document.getElementById('closePropertyPanel');
    if (cb) cb.addEventListener('click', function() {
        document.getElementById('propertyPanel').classList.add('d-none'); deselectAll();
    });
}

// ─── JointJS ────────────────────────────────────────
function initJointJS() {
    defineWorkflowNodeShape();
    graph = new joint.dia.Graph();
    const $pp = $('#paper_panel');
    paper = new joint.dia.Paper({
        el: $pp[0], model: graph, width: $pp.width(), height: $pp.height(),
        gridSize: 10, drawGrid: true, background: { color: '#fafafa' },
        linkPinning: false, snapLinks: { radius: 30 }, async: true,
        defaultLink: function() {
            var l = new joint.shapes.standard.Link();
            l.connector('smooth', { radius: 20 });
            l.router('normal');
            return l;
        },
        validateConnection: function(cvS, mS, cvT, mT, end, linkView) {
            if (!mT || cvS === cvT) return false;
            var sid = cvS.model.id, tid = cvT.model.id;
            if (graph.getLinks().some(function(l) {
                var s = l.get('source'), t = l.get('target');
                return s.id === sid && t.id === tid && s.port === mS.id && t.port === mT.id;
            })) return false;
            return true;
        },
        sorting: joint.dia.Paper.sorting.APPROX,
        viewport: function(v) { return v.model.get('type') !== 'link-tools'; },
        interactive: {
            linkMove: false, elementMove: true, arrowheadMove: false, vertexMove: false, vertexAdd: false, vertexRemove: false
        }
    });
    // Node click
    paper.on('element:pointerclick', function(ev) {
        const nd = ev.model.get('config');
        if (nd) selectNode(ev.model);
    });
    paper.on('link:pointerclick', function(lv) { selectLink(lv.model); });
    paper.on('blank:pointerclick', function() { deselectAll(); });
    // Dragover/drop
    paper.el.addEventListener('dragover', function(e) { e.preventDefault(); });
    paper.el.addEventListener('drop', function(e) {
        e.preventDefault();
        const d = e.dataTransfer.getData('text/plain');
        if (d) handleDrop(d, paper.clientToLocalPoint({ x: e.clientX, y: e.clientY }));
    });
    // Right-click
    paper.el.addEventListener('contextmenu', function(e) {
        e.preventDefault(); e.stopPropagation();
        const lp = paper.clientToLocalPoint({ x: e.clientX, y: e.clientY });
        const cv = typeof paper.findViewAt === 'function' ? paper.findViewAt(lp) : (paper.findViewFromPoint ? paper.findViewFromPoint(lp) : null);
        deselectAll();
        if (cv && cv.model.isElement()) {
            const cfg = cv.model.get('config');
            if (cfg && !cv.model.get('subgraph')) {
                selectNode(cv.model);
                showNodeContextMenu(e.clientX, e.clientY, cv.model);
                return;
            }
        }
        showBlankContextMenu(e.clientX, e.clientY, lp);
    });
    // Keyboard
    $(document).on('keydown', function(e) {
        if ((e.key === 'Delete' || e.key === 'Backspace') && !$(e.target).is('input, textarea')) deleteSelected();
        else if (e.ctrlKey || e.metaKey) {
            if (e.key === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); }
            else if (e.key === 's') { e.preventDefault(); saveGraph(); }
        }
    });
    // Watch element moves to update subgraph containers
    paper.on('element:pointerup', function() { updateSubgraphContainerPositions(); });
    initCanvasWheelZoom();
}

/** Zoom canvas toward cursor (or center when clientX/Y omitted). */
function zoomClamped(delta, clientX, clientY) {
    if (!paper) return;
    var s = paper.scale().sx;
    var newS = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, s + delta));
    if (Math.abs(newS - s) < 1e-6) return;
    if (clientX != null && clientY != null) {
        var local = paper.clientToLocalPoint({ x: clientX, y: clientY });
        var o = paper.translate();
        var beta = newS / s;
        paper.scale(newS, newS);
        paper.translate(o.tx - local.x * (beta - 1), o.ty - local.y * (beta - 1));
    } else {
        paper.scale(newS, newS);
    }
}

function initCanvasWheelZoom() {
    var targets = [
        document.getElementById('paper_panel'),
        document.getElementById('canvasContainer')
    ];
    targets.forEach(function(el) {
        if (!el) return;
        el.addEventListener('wheel', function(e) {
            if (!paper) return;
            e.preventDefault();
            var delta = e.deltaY < 0 ? ZOOM_WHEEL_STEP : -ZOOM_WHEEL_STEP;
            zoomClamped(delta, e.clientX, e.clientY);
        }, { passive: false });
    });
}

// ─── Load components ────────────────────────────────
async function loadComponents() {
    try {
        const [ar, gr, tr, lr] = await Promise.all([
            fetch('/agents/api/list'), fetch('/graph/api/list'), fetch('/tools/api/list'),
            fetch('/llms/api/list')
        ]);
        if (ar.ok) { const data = await ar.json(); data.forEach(function(a) { if (!agentsData[a.id]) agentsData[a.id] = a; }); }
        if (gr.ok) allGraphs = await gr.json();
        if (tr.ok) allTools = await tr.json();
        if (lr.ok) availableLLMs = await lr.json();
        renderComponentLists();
    } catch (e) { console.error('Load components:', e); }
}

function renderComponentLists() {
    const mkItem = function(type, icon, name, d) {
        const c = (nodeStyles[type] || nodeStyles.LLM).stroke;
        const $el = $('<div class="component-item" draggable="true">').attr({ 'data-type': type, 'data-id': d.id || '' })
            .append($('<i>').addClass('fas ' + icon).css('color', c))
            .append($('<span>').text(name));
        $el.data('data', d); return $el;
    };
    const $al = $('#agentList').empty();
    Object.values(agentsData || {}).forEach(function(a) { $al.append(mkItem('agent', 'fa-robot', a.name || a.id, a)); });
    const $sl = $('#subgraphList').empty();
    (allGraphs || []).forEach(function(g) { $sl.append(mkItem('subgraph', 'fa-project-diagram', g.name || g.id, g)); });
    const $tl = $('#toolList').empty();
    (allTools || []).forEach(function(t) { $tl.append(mkItem('tool', 'fa-wrench', t.name || t.id, t)); });
    // Wire all drag
    $('.component-item').off('dragstart').on('dragstart', function(e) {
        var $it = $(this);
        e.originalEvent.dataTransfer.setData('text/plain', JSON.stringify({
            type: $it.data('type'), id: $it.data('id'), data: $it.data('data')
        }));
    });
}

// ─── Drop handler ───────────────────────────────────
function handleDrop(dataStr, pos) {
    try {
        var d = JSON.parse(dataStr), id, cfg;
        if (d.type === 'start') {
            id = 'START'; cfg = { id: 'START', name: 'START', type: 'flow', inputs: [], outputs: [] };
            _addNode(id, cfg, pos);
        } else if (d.type === 'end') {
            id = 'END'; cfg = { id: 'END', name: 'END', type: 'flow', inputs: [], outputs: [] };
            _addNode(id, cfg, pos);
        } else if (d.type === 'agent') {
            id = d.id;
            if (!agentsData[id]) { var aname = d.data ? d.data.name || d.id : d.id; agentsData[id] = { id: id, name: aname, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } }; }
            cfg = agentsData[id];
            _addNode(id, cfg, pos);
        } else if (d.type === 'subgraph' || d.type === 'loop') {
            id = d.id || d.type + '_' + (++nodeCounter);
            var srcData = (d.type === 'subgraph' && d.data && d.data.nodes) ? d.data : null;
            if (!srcData && d.data && d.data.id && graphsById && graphsById[d.data.id]) srcData = graphsById[d.data.id];
            var sgName = (d.data && d.data.name) || d.id || (d.type === 'loop' ? 'Loop' : 'Subgraph');
            var sgId = id;
            agentsData[sgId] = { id: sgId, name: sgName, type: (d.type === 'loop' ? 'loop' : 'SUB'), inputs: ['input'], outputs: { name: 'output', type: 'list' } };
            _expandSubgraphAt(sgId, srcData, pos);
        } else if (d.type === 'branch') {
            id = 'branch_' + (++nodeCounter);
            cfg = { id: id, name: 'Branch', type: 'branch', inputs: ['input'], outputs: { name: 'output', type: 'dict' }, conditions: [{ label: 'True', condition: 'true' }, { label: 'False', condition: 'false' }] };
            _addNode(id, cfg, pos);
        } else if (d.type === 'tool') {
            id = d.id; cfg = { id: id, name: d.data ? d.data.name || d.id : 'Tool', type: 'tool', inputs: (d.data && d.data.inputs) || [], outputs: { name: 'output', type: 'str' } };
            _addNode(id, cfg, pos);
        } else {
            id = d.type + '_' + (++nodeCounter);
            cfg = { id: id, name: id, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
            _addNode(id, cfg, pos);
        }
    } catch (e) { console.error('Drop:', e); }
}

function _addNode(id, cfg, pos) {
    if (!agentsData[id]) agentsData[id] = cfg;
    var el = createNode(id);
    el.position(pos.x, pos.y);
    graph.addCell(el);
    saveToHistory();
}

// ─── Expand subgraph at drop position ────────────────
function _expandSubgraphAt(sgId, srcData, pos) {
    if (!srcData || !srcData.nodes || !srcData.nodes.length) {
        // Empty loop/subgraph: create range and container, no inner nodes
        subgraphRanges[sgId] = { nodes: [], subgraphs: [] };
        _drawSubgraphContainer(sgId);
        saveToHistory();
        return;
    }
    // Build agentsData entries for each node in subgraph
    (srcData.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        if (!agentsData[nid]) agentsData[nid] = { id: nid, name: nid, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
    });
    // Create the subgraph range
    subgraphRanges[sgId] = { nodes: (srcData.nodes || []).filter(function(n) { return n !== 'START' && n !== 'END'; }), subgraphs: [] };
    // Place internal nodes at relative positions
    var x0 = pos.x + 50, y0 = pos.y + 40;
    var idx = 0;
    (srcData.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        var el = createNode(nid);
        el.position(x0 + (idx % 2) * 200, y0 + Math.floor(idx / 2) * 100);
        graph.addCell(el);
        idx++;
    });
    // Draw container
    _drawSubgraphContainer(sgId);
    saveToHistory();
}

// ─── Create node ────────────────────────────────────
function createNode(id) {
    var isSE = id === 'START' || id === 'END';
    var agent = agentsData[id];
    if (!agent && !isSE) {
        agent = agentsData[id] = { id: id, name: id, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
    }
    if (isSE) {
        var stroke = nodeStyles.startEnd.stroke;
        var label = id;
        return new joint.shapes.standard.Rectangle({
            id: id, size: { width: 88, height: 88 },
            attrs: {
                body: { fill: stroke, stroke: stroke, strokeWidth: 2, rx: 44, ry: 44 },
                label: {
                    text: label, fill: '#fff', fontSize: 13, fontWeight: 'bold',
                    textAnchor: 'middle', textVerticalAnchor: 'middle',
                    textWrap: { width: 72, height: 40, ellipsis: true }
                }
            },
            ports: {
                groups: {
                    out: { position: 'right', attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: stroke, strokeWidth: 2 } } },
                    in:  { position: 'left',  attrs: { circle: { r: 5, magnet: true, fill: '#fff', stroke: stroke, strokeWidth: 2 } } }
                },
                items: id === 'START'
                    ? [{ id: 'out_trigger', group: 'out' }]
                    : [{ id: 'in_input', group: 'in' }]
            },
            config: { id: id, name: label, type: 'flow', inputs: [], outputs: [] }
        });
    }

    var layout = buildNodeLayout(id, agent);
    var el = new joint.shapes.neuragraph.WorkflowNode({
        id: id,
        size: { width: layout.width, height: layout.height },
        attrs: {
            fo: { width: layout.width, height: layout.height },
            body: { stroke: layout.stroke, strokeWidth: 1.5 },
            content: { html: layout.html }
        },
        ports: { groups: WF_PORT_GROUPS, items: layout.portItems },
        config: layout.config,
        prompt: (agent && agent.prompt_template) || {}
    });
    return el;
}

// ─── Link ───────────────────────────────────────────
function createLink(sourceId, targetId, opts) {
    opts = opts || inferLinkPorts(sourceId, targetId);
    var link = new joint.shapes.standard.Link();
    var srcRef = { id: sourceId };
    var tgtRef = { id: targetId };
    if (opts.sourcePort) srcRef.port = opts.sourcePort;
    if (opts.targetPort) tgtRef.port = opts.targetPort;
    link.source(srcRef);
    link.target(tgtRef);
    var srcCell = graph.getCell(sourceId);
    var color = '#666', sn = srcCell;
    if (sn) { var st = sn.get('config') ? sn.get('config').type : 'PGM'; color = (nodeStyles[st] || nodeStyles.PGM).stroke; }
    link.attr({
        line: {
            stroke: color, strokeWidth: 2,
            targetMarker: { type: 'path', d: 'M 10 -5 0 0 10 5 z', fill: color }
        },
        wrapper: { strokeWidth: 8, stroke: 'transparent', fill: 'none' }
    });
    link.connector('smooth', { radius: 20 });
    link.router('normal');
    return link;
}

function reattachLinkPorts() {
    graph.getLinks().forEach(function(link) {
        var src = link.get('source'), tgt = link.get('target');
        if (!src || !tgt || !src.id || !tgt.id) return;
        var opts = inferLinkPorts(src.id, tgt.id);
        link.source(resolvePortEndpoint(graph.getCell(src.id), 'out', opts.sourcePort));
        link.target(resolvePortEndpoint(graph.getCell(tgt.id), 'in', opts.targetPort));
    });
}

function inferLinkPorts(sourceId, targetId) {
    var opts = {};
    var srcCfg = (agentsData[sourceId]) || (graph.getCell(sourceId) && graph.getCell(sourceId).get('config'));
    var tgtCfg = (agentsData[targetId]) || (graph.getCell(targetId) && graph.getCell(targetId).get('config'));
    if (srcCfg) {
        if ((srcCfg.flowKind === 'branch' || srcCfg.type === 'branch') && srcCfg.conditions && srcCfg.conditions.length) {
            opts.sourcePort = 'out_' + sanitizePortId(srcCfg.conditions[0].label);
        } else if (srcCfg.outputs && srcCfg.outputs.name) {
            opts.sourcePort = 'out_' + srcCfg.outputs.name;
        }
    }
    if (tgtCfg && tgtCfg.inputs && tgtCfg.inputs.length) {
        var outName = srcCfg && srcCfg.outputs ? srcCfg.outputs.name : null;
        if (outName && tgtCfg.inputs.indexOf(outName) >= 0) {
            opts.targetPort = 'in_' + outName;
        } else {
            opts.targetPort = 'in_' + tgtCfg.inputs[0];
        }
    }
    return opts;
}

// ─── Render workflow ────────────────────────────────
function collectSubgraphInnerNodes() {
    var inner = [];
    Object.keys(subgraphRanges).forEach(function(sgId) {
        (subgraphRanges[sgId].nodes || []).forEach(function(n) {
            if (inner.indexOf(n) < 0) inner.push(n);
        });
    });
    return inner;
}

function renderWorkflow(wf) {
    if (!wf || !wf.nodes || !wf.edges) { createDefaultWorkflow(); return; }
    graph.clear(); subgraphRanges = {};
    mergeFlowNodesFromGraph(wf);
    var expanded = expandSubgraph(wf);
    var innerFromSubs = collectSubgraphInnerNodes();
    var topNodes = expanded.nodes.filter(function(n) { return n !== 'START' && n !== 'END'; });
    innerFromSubs.forEach(function(n) { if (topNodes.indexOf(n) < 0) topNodes.push(n); });
    var allNodes = ['START'].concat(topNodes, ['END']);
    var nodeCells = allNodes.map(function(id) { return createNode(id); });
    var linkCells = [];
    expanded.edges.forEach(function(e) {
        if (graph.getCell(e[0]) || allNodes.indexOf(e[0]) >= 0)
            if (graph.getCell(e[1]) || allNodes.indexOf(e[1]) >= 0)
                linkCells.push(createLink(e[0], e[1]));
    });
    graph.resetCells(nodeCells.concat(linkCells));
    joint.layout.DirectedGraph.layout(graph, {
        rankDir: 'LR', nodeSep: 90, rankSep: 160, edgeSep: 50, marginX: 40, marginY: 40
    });
    reattachLinkPorts();
    drawSubgraphContainers();
    fitToContent(); saveToHistory();
}

// ─── Subgraph expand ────────────────────────────────
function expandSubgraph(wf) {
    var nodes = [], edges = [];
    subgraphRanges = {};
    var isSub = function(nid) {
        if (getNodeFlowKind(nid, wf) === 'loop') return true;
        if (agentsData[nid] && agentsData[nid].type === 'SUB') return true;
        if (graphsById && graphsById[nid]) return true;
        if (wf.visualData && wf.visualData.nodes) {
            var vn = wf.visualData.nodes.find(function(n) { return n.id === nid || n.originalId === nid; });
            if (vn && (vn.type === 'subgraph' || vn.type === 'loop' ||
                (vn.data && (vn.data.type === 'SUB' || vn.data.type === 'loop')))) return true;
        }
        return false;
    };
    var ensureRange = function(nid) { if (!subgraphRanges[nid]) subgraphRanges[nid] = { nodes: [], subgraphs: [] }; };
    var getEntries = function(subId) {
        var sub = (graphsById && graphsById[subId]) || (wf.visualData && wf.visualData.nodes ? (wf.visualData.nodes.find(function(n) { return n.id === subId || n.originalId === subId; }) || {}).data : null);
        if (!sub || !sub.edges) return [];
        return sub.edges.filter(function(e) { return e[0] === 'START'; }).map(function(e) { return e[1]; }).reduce(function(a, t) { return a.concat(isSub(t) ? getEntries(t) : [t]); }, []);
    };
    var getExits = function(subId) {
        var sub = (graphsById && graphsById[subId]) || (wf.visualData && wf.visualData.nodes ? (wf.visualData.nodes.find(function(n) { return n.id === subId || n.originalId === subId; }) || {}).data : null);
        if (!sub || !sub.edges) return [];
        return sub.edges.filter(function(e) { return e[1] === 'END'; }).map(function(e) { return e[0]; }).reduce(function(a, s) { return a.concat(isSub(s) ? getExits(s) : [s]); }, []);
    };
    var expandRecursive = function(subId) {
        var sub = (graphsById && graphsById[subId]) || (wf.visualData && wf.visualData.nodes ? (wf.visualData.nodes.find(function(n) { return n.id === subId || n.originalId === subId; }) || {}).data : null);
        if (!sub) return;
        ensureRange(subId);
        (sub.nodes || []).forEach(function(n) {
            if (n === 'START' || n === 'END') return;
            if (isSub(n)) { ensureRange(n); subgraphRanges[subId].subgraphs.push(n); expandRecursive(n); }
            else { nodes.push(n); subgraphRanges[subId].nodes.push(n); }
        });
        (sub.edges || []).forEach(function(e) {
            if (e[0] === 'START' || e[1] === 'END') return;
            var se = e[0], te = e[1];
            if (!isSub(se) && !isSub(te)) edges.push([se, te]);
            else if (!isSub(se) && isSub(te)) getEntries(te).forEach(function(et) { edges.push([se, et]); });
            else if (isSub(se) && !isSub(te)) getExits(se).forEach(function(es) { edges.push([es, te]); });
            else getExits(se).forEach(function(es) { getEntries(te).forEach(function(et) { edges.push([es, et]); }); });
        });
    };
    (wf.nodes || []).forEach(function(nid) { if (isSub(nid)) expandRecursive(nid); else nodes.push(nid); });
    (wf.edges || []).forEach(function(e) {
        var sArr = Array.isArray(e[0]) ? e[0] : [e[0]], tArr = Array.isArray(e[1]) ? e[1] : [e[1]];
        sArr.forEach(function(s) { tArr.forEach(function(t) {
            if (!isSub(s) && !isSub(t)) edges.push([s, t]);
            else if (!isSub(s) && isSub(t)) getEntries(t).forEach(function(et) { edges.push([s, et]); });
            else if (isSub(s) && !isSub(t)) getExits(s).forEach(function(es) { edges.push([es, t]); });
            else getExits(s).forEach(function(es) { getEntries(t).forEach(function(et) { edges.push([es, et]); }); });
        }); });
    });
    var uniq = Array.from(new Set(nodes)), ns = new Set(uniq.concat(['START', 'END']));
    return { nodes: uniq, edges: edges.filter(function(e) { return ns.has(e[0]) && ns.has(e[1]); }) };
}

function getSubgraphDepth(id, depth) {
    if (depth === undefined) depth = 0;
    for (var k in subgraphRanges) if (subgraphRanges[k].subgraphs && subgraphRanges[k].subgraphs.indexOf(id) >= 0) return getSubgraphDepth(k, depth + 1);
    return depth;
}

// ─── Draw subgraph containers with group-drag ────────
function drawSubgraphContainers() {
    var ordered = Object.keys(subgraphRanges).sort(function(a, b) { return getSubgraphDepth(b) - getSubgraphDepth(a); });
    ordered.forEach(function(subId) {
        _drawSubgraphContainer(subId);
    });
}

function _containerBBox(subId) {
    var info = subgraphRanges[subId];
    if (!info) return null;
    var bbox = null;
    (info.nodes || []).forEach(function(nid) {
        var el = graph.getCell(nid);
        if (el) bbox = bbox ? bbox.union(el.getBBox()) : el.getBBox();
    });
    (info.subgraphs || []).forEach(function(childId) {
        var childCnt = graph.getCell(childId + '_container');
        if (childCnt) {
            var cb = childCnt.getBBox();
            bbox = bbox ? bbox.union(cb) : cb;
        } else {
            var nested = _containerBBox(childId);
            if (nested) {
                if (!bbox) {
                    bbox = { x: nested.x, y: nested.y, width: nested.width, height: nested.height };
                } else {
                    var x1 = Math.min(bbox.x, nested.x);
                    var y1 = Math.min(bbox.y, nested.y);
                    var x2 = Math.max(bbox.x + bbox.width, nested.x + nested.width);
                    var y2 = Math.max(bbox.y + bbox.height, nested.y + nested.height);
                    bbox = { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
                }
            }
        }
    });
    return bbox;
}

function _drawSubgraphContainer(subId) {
    var info = subgraphRanges[subId];
    if (!info) return;
    var old = graph.getCell(subId + '_container');
    if (old) old.remove();
    var bbox = _containerBBox(subId);
    if (!bbox) {
        bbox = { x: 0, y: 0, width: 200, height: 120 };
    }
    var pad = 52;
    var cntId = subId + '_container';
    var rect = new joint.shapes.standard.Rectangle({
        id: cntId, z: -10,
        position: { x: bbox.x - pad, y: bbox.y - pad },
        size: { width: bbox.width + pad * 2, height: bbox.height + pad * 2 },
        attrs: {
            body: { fill: 'rgba(118,75,162,0.08)', stroke: '#764ba2', strokeDasharray: '8 4', rx: 14, ry: 14, strokeWidth: 1.5 },
            label: {
                text: (getGraphFlowNodes()[subId] && getGraphFlowNodes()[subId].name) ||
                    (agentsData[subId] ? agentsData[subId].name : subId),
                fill: '#764ba2', fontSize: 13, fontWeight: 'bold', refX: 14, refY: 14,
                textAnchor: 'start', textVerticalAnchor: 'top'
            }
        },
        subgraph: subId
    });
    graph.addCell(rect);
}

// ─── Update container positions when elements move ──
function updateSubgraphContainerPositions() {
    var ordered = Object.keys(subgraphRanges).sort(function(a, b) {
        return getSubgraphDepth(b) - getSubgraphDepth(a);
    });
    ordered.forEach(function(subId) {
        var bbox = _containerBBox(subId);
        var cnt = graph.getCell(subId + '_container');
        if (!cnt || !bbox) return;
        var pad = 52;
        cnt.position(bbox.x - pad, bbox.y - pad);
        cnt.resize(bbox.width + pad * 2, bbox.height + pad * 2);
    });
}

// ─── Selection ──────────────────────────────────────
function selectNode(node) {
    deselectAll();
    selectedCell = node;
    var cfg = node.get('config');
    if (cfg && cfg.id && cfg.type !== 'flow') {
        applyNodeVisual(node, buildNodeLayout(cfg.id, agentsData[cfg.id] || cfg), true);
    } else {
        node.attr('body/stroke', '#ff5722');
        node.attr('body/strokeWidth', 3);
    }
    showPropertyPanel(node);
}
function selectLink(link) { deselectAll(); selectedCell = link; link.attr('line/strokeWidth', 4); }
function deselectAll() {
    if (selectedCell) {
        if (selectedCell.isElement()) {
            var cfg = selectedCell.get('config');
            if (cfg && cfg.type === 'flow') {
                selectedCell.attr('body/stroke', nodeStyles.startEnd.stroke);
                selectedCell.attr('body/strokeWidth', 2);
            } else if (cfg && cfg.id) {
                var layout = buildNodeLayout(cfg.id, agentsData[cfg.id] || cfg);
                applyNodeVisual(selectedCell, layout, false);
            }
        } else {
            selectedCell.attr('line/strokeWidth', 2);
        }
    }
    selectedCell = null; hidePropertyPanel();
}

// ─── LLM model selector (property panel) ────────────
function findLlmConfig(llmId) {
    return availableLLMs.find(function(l) { return l.id === llmId; }) || null;
}

function buildLlmSelectorHtml(selectedId) {
    var html = '<div class="mb-2"><label class="fw-bold small">LLM config (meta/llms)</label>';
    html += '<select id="propLlmSelect" class="form-select form-select-sm">';
    html += '<option value="">-- Select LLM config --</option>';
    availableLLMs.forEach(function(llm) {
        var label = llm.id + ' · ' + (llm.model || '') + ' · ' + (llm.type || 'custom');
        html += '<option value="' + escHtml(llm.id) + '"' + (selectedId === llm.id ? ' selected' : '') + '>' + escHtml(label) + '</option>';
    });
    html += '</select>';
    html += '<div id="propLlmLinkPreview" class="small text-muted mt-1" style="word-break:break-all;"></div>';
    html += '<a id="propLlmEditLink" class="small" href="#" target="_blank" rel="noopener">Edit LLM config</a>';
    html += '</div>';
    return html;
}

function updateLlmLinkPreview(llmId) {
    var llm = findLlmConfig(llmId);
    var $prev = $('#propLlmLinkPreview');
    var $link = $('#propLlmEditLink');
    if (!llm) {
        $prev.text('No LLM config selected');
        $link.attr('href', '#').hide();
        return;
    }
    $prev.html(
        '<strong>API:</strong> ' + escHtml(llm.base_url || '(none)') + '<br>' +
        '<strong>Model:</strong> ' + escHtml(llm.model || '') + '<br>' +
        '<strong>Type:</strong> ' + escHtml(llm.type || '')
    );
    $link.attr('href', '/llms/' + encodeURIComponent(llm.id) + '/edit').show();
}

function bindLlmSelectorEvents(agentId) {
    $('#propLlmSelect').off('change').on('change', function() {
        var llmId = $(this).val();
        var node = graph.getCell(agentId);
        if (!node) return;
        var cfg = node.get('config') || {};
        cfg.model = llmId;
        node.set('config', cfg);
        if (agentsData[agentId]) agentsData[agentId].model = llmId;
        updateLlmLinkPreview(llmId);
        refreshNodeVisual(agentId);
    });
}

// ─── Property panel ─────────────────────────────────
function showPropertyPanel(node) {
    $('#propertyPanel').removeClass('d-none');
    var cfg = node.get('config') || {}, prompt = node.get('prompt') || {};
    var type = cfg.type || 'Unknown', id = cfg.id || node.id, name = cfg.name || id;
    $('#propName').val(name);
    var showIO = ['LLM','PGM','branch','loop','tool','SUB'].indexOf(type) >= 0 || (cfg.inputs && cfg.inputs.length > 0);
    $('#ioMappingSection').toggle(showIO);
    var icon = typeIcons[type] || 'fa-cube';
    var html = '<div class="card mb-3"><div class="card-header bg-primary text-white"><h6 class="mb-0"><i class="fas ' + icon + ' me-2"></i>' + name + '</h6></div><div class="card-body">';
    html += '<div class="mb-2"><label class="fw-bold small">ID</label><input class="form-control form-control-sm" value="' + id + '" readonly></div>';
    html += '<div class="mb-2"><label class="fw-bold small">Type</label><span class="badge ms-2 ' + (type==='LLM'?'bg-indigo':type==='PGM'?'bg-success':type==='SUB'?'bg-purple':type==='branch'?'bg-warning':type==='loop'?'bg-info':'bg-secondary') + '">' + type + '</span></div>';
    if (type === 'LLM') html += buildLlmSelectorHtml(cfg.model || '');
    html += '<div class="mb-2"><label class="fw-bold small">Inputs</label><input class="form-control form-control-sm editable-field" data-field="inputs" value="' + ((cfg.inputs||[]).join(', ')) + '"></div>';
    if (cfg.outputs) html += '<div class="mb-2"><label class="fw-bold small">Outputs</label><div class="row g-1"><div class="col-6"><input class="form-control form-control-sm editable-field" data-field="outputs_name" value="' + (cfg.outputs.name||'') + '" placeholder="name"></div><div class="col-6"><input class="form-control form-control-sm editable-field" data-field="outputs_type" value="' + (cfg.outputs.type||'') + '" placeholder="type"></div></div></div>';
    if (cfg.persistence && (cfg.persistence.file_path || cfg.persistence.file_type)) html += '<div class="mb-2"><label class="fw-bold small">Persistence</label><div class="row g-1"><div class="col-8"><input class="form-control form-control-sm editable-field" data-field="persistence_file_path" value="' + (cfg.persistence.file_path||'') + '"></div><div class="col-4"><input class="form-control form-control-sm editable-field" data-field="persistence_file_type" value="' + (cfg.persistence.file_type||'') + '"></div></div></div>';
    html += '</div></div>';
    if (type === 'LLM') {
        html += '<div class="card mb-3"><div class="card-header bg-info text-white"><h6 class="mb-0"><i class="fas fa-file-alt me-2"></i>Prompt</h6></div><div class="card-body">';
        html += '<div class="mb-2"><label class="fw-bold small">Description</label><textarea class="form-control form-control-sm editable-field" data-field="prompt_description" rows="2">' + (prompt.description||'') + '</textarea></div>';
        html += '<div class="mb-2"><label class="fw-bold small">System Prompt</label><textarea class="form-control form-control-sm editable-field" data-field="prompt_system" rows="4">' + (prompt.system||'') + '</textarea></div>';
        html += '<div class="mb-2"><label class="fw-bold small">Human Prompt</label><textarea class="form-control form-control-sm editable-field" data-field="prompt_human" rows="6">' + (prompt.human||'') + '</textarea></div>';
        if (prompt.relation_schema) html += '<div class="mb-2"><label class="fw-bold small">Relation Schema</label><div class="row g-1"><div class="col-6"><input class="form-control form-control-sm editable-field" data-field="rel_head_type" value="' + (prompt.relation_schema.head_type||'') + '"></div><div class="col-6"><input class="form-control form-control-sm editable-field" data-field="rel_tail_type" value="' + (prompt.relation_schema.tail_type||'') + '"></div></div></div>';
        html += '</div></div>';
    }
    if ((cfg.flowKind === 'branch' || type === 'branch') && cfg.conditions) {
        html += '<div class="card mb-3"><div class="card-header bg-warning text-dark"><h6 class="mb-0"><i class="fas fa-code-branch me-2"></i>Conditions</h6></div><div class="card-body">';
        cfg.conditions.forEach(function(c,i) { html += '<div class="mb-2"><span class="badge bg-warning me-1">' + c.label + '</span><input class="form-control form-control-sm d-inline-block w-75 editable-field" data-field="cond_' + i + '" value="' + (c.condition||'') + '" placeholder="e.g. {{ score }} > 0.5"></div>'; });
        html += '</div></div>';
    }
    if ((cfg.flowKind === 'loop' || type === 'loop') && cfg.loopConfig) {
        var lc = cfg.loopConfig;
        html += '<div class="card mb-3"><div class="card-header bg-info text-white"><h6 class="mb-0"><i class="fas fa-redo me-2"></i>Loop Config</h6></div><div class="card-body">';
        html += '<div class="mb-2"><label class="fw-bold small">Loop Type</label><select class="form-control form-control-sm editable-field" data-field="loop_type">';
        ['for','while','foreach'].forEach(function(t) { html += '<option value="' + t + '"' + (lc.loopType===t?' selected':'') + '>' + t + '</option>'; });
        html += '</select></div>';
        if (lc.loopType === 'for') html += '<div class="mb-2"><label class="fw-bold small">Count</label><input class="form-control form-control-sm editable-field" data-field="loop_count" value="' + (lc.count||10) + '" type="number"></div>';
        html += '</div></div>';
    }
    if (cfg.tools && cfg.tools.length) html += '<div class="card mb-3"><div class="card-header bg-secondary text-white"><h6 class="mb-0">Tools</h6></div><div class="card-body">' + cfg.tools.map(function(t){return '<span class="badge bg-dark me-1">' + t + '</span>';}).join('') + '</div></div>';
    html += '<div class="d-grid gap-2"><button class="btn btn-primary btn-sm" onclick="saveAgentChanges(\'' + id + '\')"><i class="fas fa-save me-2"></i>Save</button></div>';
    $('#typeSpecificProps').html(html);
    if (type === 'LLM') {
        updateLlmLinkPreview(cfg.model || '');
        bindLlmSelectorEvents(id);
    }
    renderIOMapping(node);
}
function getUpstreamNodeIds(nodeId) {
    var ups = [];
    graph.getLinks().forEach(function(l) {
        var t = l.get('target'), s = l.get('source');
        if (t && t.id === nodeId && s && s.id && s.id !== 'START') ups.push(s.id);
    });
    return ups;
}

function renderIOMapping(node) {
    var cfg = node.get('config') || {}, nid = cfg.id || node.id;
    var inputs = cfg.inputs || [], outName = cfg.outputs ? cfg.outputs.name : 'output';
    var bindings = graphBindings[nid] || {};
    var upstream = getUpstreamNodeIds(nid);
    var $ic = $('#inputMapping').empty(), $oc = $('#outputPreview').empty();
    if (upstream.length) {
        $ic.append('<p class="small text-muted mb-2">Upstream: <code>' + escHtml(upstream.join(', ')) + '</code></p>');
    }
    inputs.forEach(function(inp) {
        var val = bindings[inp] || '';
        if (!val && upstream.length) {
            val = '{{ ' + upstream[0] + '.' + inp + ' }}';
        }
        $ic.append(
            '<div class="d-flex align-items-center mb-2">' +
            '<span class="badge bg-secondary me-2" style="min-width:60px">' + escHtml(inp) + '</span>' +
            '<input class="form-control form-control-sm flex-grow-1 mapping-input" data-input="' + escHtml(inp) + '" value="' + escHtml(val) + '" placeholder="e.g., {{ node.field }}">' +
            '</div>'
        );
    });
    if (!inputs.length) $ic.html('<p class="text-muted small mb-0">No inputs</p>');
    $oc.append('<div class="d-flex align-items-center mb-1"><span class="badge bg-success me-2" style="min-width:60px">' + escHtml(outName) + '</span><code class="small text-muted">{{ ' + escHtml(nid) + '.' + escHtml(outName) + ' }}</code></div>');
    $('.mapping-input').off('change').on('change', function() {
        var field = $(this).data('input');
        if (!graphBindings[nid]) graphBindings[nid] = {};
        graphBindings[nid][field] = $(this).val();
    });
}
function hidePropertyPanel() { document.getElementById('propertyPanel').classList.add('d-none'); }

function saveAgentChanges(agentId) {
    var node = graph.getCell(agentId); if (!node) return;
    var cfg = node.get('config') || {}, prompt = node.get('prompt') || {};
    var llmSel = $('#propLlmSelect').val();
    if (llmSel) cfg.model = llmSel;
    $('#typeSpecificProps .editable-field').each(function() {
        var $f = $(this), field = $f.data('field'), val = $f.val(); if (!field) return;
        if (field === 'inputs') cfg.inputs = val.split(',').map(function(s){return s.trim();}).filter(Boolean);
        else if (field === 'outputs_name') { if (!cfg.outputs) cfg.outputs = {}; cfg.outputs.name = val; }
        else if (field === 'outputs_type') { if (!cfg.outputs) cfg.outputs = {}; cfg.outputs.type = val; }
        else if (field === 'persistence_file_path') { if (!cfg.persistence) cfg.persistence = {}; cfg.persistence.file_path = val; }
        else if (field === 'persistence_file_type') { if (!cfg.persistence) cfg.persistence = {}; cfg.persistence.file_type = val; }
        else if (field === 'prompt_description') prompt.description = val;
        else if (field === 'prompt_system') prompt.system = val;
        else if (field === 'prompt_human') prompt.human = val;
        else if (field === 'rel_head_type') { if (!prompt.relation_schema) prompt.relation_schema = {}; prompt.relation_schema.head_type = val; }
        else if (field === 'rel_tail_type') { if (!prompt.relation_schema) prompt.relation_schema = {}; prompt.relation_schema.tail_type = val; }
    });
    cfg.prompt_template = prompt;
    node.set('config', cfg);
    node.set('prompt', prompt);
    if (agentsData[agentId]) {
        Object.assign(agentsData[agentId], cfg);
        agentsData[agentId].prompt_template = prompt;
    }
    refreshNodeVisual(agentId);
    $.ajax({
        url: '/agents/api/save', method: 'POST', contentType: 'application/json',
        data: JSON.stringify({
            id: agentId, name: cfg.name, type: cfg.type, model: cfg.model,
            inputs: cfg.inputs, outputs: cfg.outputs, persistence: cfg.persistence,
            prompt_template: prompt, tools: cfg.tools, conditions: cfg.conditions,
            loopConfig: cfg.loopConfig
        }),
        success: function(r) { alert(r.success ? 'Saved!' : 'Failed: ' + (r.error || 'Unknown')); },
        error: function(x) { alert('Error: ' + (x.responseJSON ? x.responseJSON.error : x.statusText)); }
    });
    saveToHistory();
}

// ─── Zoom / History ─────────────────────────────────
function resetView() { paper.scale(1, 1); paper.translate(0, 0); }
function fitToContent() {
    var bbox = graph.getBBox(), pw = paper.el.clientWidth, ph = paper.el.clientHeight;
    if (bbox) { var sc = Math.min(pw/bbox.width, ph/bbox.height) * 0.9; paper.scale(sc, sc); paper.translate(-bbox.x*sc+(pw-bbox.width*sc)/2, -bbox.y*sc+(ph-bbox.height*sc)/2); }
}
function saveToHistory() { historyStack.push(JSON.stringify(graph.toJSON())); redoStack = []; $('#btnUndo').prop('disabled', false); }
function undo() { if (historyStack.length <= 1) return; redoStack.push(historyStack.pop()); graph.fromJSON(JSON.parse(historyStack[historyStack.length-1])); deselectAll(); }
function redo() { if (!redoStack.length) return; historyStack.push(redoStack.pop()); graph.fromJSON(JSON.parse(historyStack[historyStack.length-1])); deselectAll(); }
function deleteSelected() { if (!selectedCell || !confirm('Delete?')) return; graph.getConnectedLinks(selectedCell).forEach(function(l) { l.remove(); }); selectedCell.remove(); selectedCell = null; hidePropertyPanel(); saveToHistory(); }

// ─── Context menus ──────────────────────────────────
var $contextMenu = $('<div id="customContextMenu">').css({ position:'fixed', background:'#fff', border:'1px solid #e0e0e0', boxShadow:'0 8px 24px rgba(0,0,0,0.15)', display:'none', zIndex:10000, borderRadius:'8px', padding:'6px 0', minWidth:'200px' }).appendTo('body');
function showMenu(x, y, items) {
    $contextMenu.empty();
    items.forEach(function(item) {
        if (item.divider) $('<div>').css({ height:'1px', background:'#eee', margin:'4px 12px' }).appendTo($contextMenu);
        else $('<div>').css({ padding:'10px 18px', cursor:'pointer', fontSize:'14px', display:'flex', alignItems:'center', color:'#333' })
            .on('mouseenter', function() { $(this).css('background','#f3f4f6'); })
            .on('mouseleave', function() { $(this).css('background','#fff'); })
            .on('click', function() { item.action(); $contextMenu.hide(); })
            .append($('<i>').addClass('fas '+(item.icon||'fa-circle')).css({ marginRight:'10px', color:'#6b7280', width:'18px', textAlign:'center' }))
            .append($('<span>').text(item.label)).appendTo($contextMenu);
    });
    var mw = $contextMenu.outerWidth() || 200, mh = $contextMenu.outerHeight() || 400;
    var ww = $(window).width(), wh = $(window).height();
    $contextMenu.css({ left: Math.max(0, Math.min(x, ww-mw-10))+'px', top: Math.max(0, Math.min(y, wh-mh-10))+'px', display:'block' });
    $(document).one('click', function() { $contextMenu.hide(); });
}
function showBlankContextMenu(x, y, lp) {
    showMenu(x, y, [
        { label:'Create Agent', icon:'fa-robot', action: function() {
            var aid = prompt('Agent ID:') || 'agent_'+(++nodeCounter);
            if (!agentsData[aid]) agentsData[aid] = { id:aid, name:aid, type:'LLM', inputs:[], outputs:{ name:'output', type:'str' } };
            var el = createNode(aid); el.position(lp.x, lp.y); graph.addCell(el); saveToHistory();
        }},
        { label:'Create Branch', icon:'fa-code-branch', action: function() {
            var bid = 'branch_'+(++nodeCounter);
            agentsData[bid] = { id:bid, name:'Branch', type:'branch', inputs:['input'], outputs:{ name:'output', type:'dict' }, conditions:[{ label:'True', condition:'true' },{ label:'False', condition:'false' }] };
            var el = createNode(bid); el.position(lp.x, lp.y); graph.addCell(el); saveToHistory();
        }},
        { label:'Create Loop', icon:'fa-redo', action: function() {
            var lid = 'loop_'+(++nodeCounter);
            agentsData[lid] = { id:lid, name:'Loop', type:'loop', inputs:['input'], outputs:{ name:'output', type:'list' }, loopConfig:{ loopType:'for', count:10 } };
            subgraphRanges[lid] = { nodes:[], subgraphs:[] };
            _drawSubgraphContainer(lid);
            saveToHistory();
        }},
        { divider:true },
        { label:'Export as SVG', icon:'fa-file-image', action: downloadSVG },
        { label:'Export as PNG', icon:'fa-image', action: downloadPNG },
        { divider:true },
        { label:'Fit to Content', icon:'fa-expand', action: fitToContent },
        { label:'Reset View', icon:'fa-sync', action: resetView }
    ]);
}
function showNodeContextMenu(x, y, node) {
    var cfg = node.get('config') || {};
    showMenu(x, y, [
        { label:'Node: '+(cfg.name||node.id), icon:'fa-cube', action: function(){} },
        { divider:true },
        { label:'View Properties', icon:'fa-edit', action: function() { showPropertyPanel(node); } },
        { label:'Delete Node', icon:'fa-trash', action: function() {
            if (confirm('Delete?')) { graph.getConnectedLinks(node).forEach(function(l){l.remove();}); node.remove(); deselectAll(); hidePropertyPanel(); saveToHistory(); }
        }}
    ]);
}

// ─── Export ─────────────────────────────────────────
function downloadSVG() { var bb=graph.getBBox(),p=20,svg=paper.svg.cloneNode(true);svg.setAttribute('viewBox',(bb.x-p)+' '+(bb.y-p)+' '+(bb.width+p*2)+' '+(bb.height+p*2));svg.setAttribute('width',bb.width+p*2);svg.setAttribute('height',bb.height+p*2);svg.setAttribute('xmlns','http://www.w3.org/2000/svg');var b=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='workflow.svg';a.click(); }
function downloadPNG() { var bb=graph.getBBox(),p=20,s=2,svg=paper.svg.cloneNode(true);svg.setAttribute('viewBox',(bb.x-p)+' '+(bb.y-p)+' '+(bb.width+p*2)+' '+(bb.height+p*2));svg.setAttribute('width',(bb.width+p*2)*s);svg.setAttribute('height',(bb.height+p*2)*s);var c=document.createElement('canvas');c.width=(bb.width+p*2)*s;c.height=(bb.height+p*2)*s;var ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.scale(s,s);var img=new Image(),url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'}));img.onload=function(){ctx.drawImage(img,0,0);URL.revokeObjectURL(url);c.toBlob(function(b){var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='workflow.png';a.click();},'image/png');};img.src=url; }

// ─── Save / serialize ──────────────────────────────
function saveGraph() {
    var wd = serializeGraph(); wd.id = current || prompt('Workflow ID:') || 'new_workflow'; wd.name = $('#currentWorkflowName').text();
    if (!wd.id) return alert('ID required');
    $.ajax({ url:'/graph/api/save', method:'POST', contentType:'application/json', data: JSON.stringify(wd), success: function(r) { alert(r.success?'Saved!':'Failed: '+(r.error||'Unknown')); }, error: function(x) { alert('Error: '+(x.responseJSON?x.responseJSON.error:x.statusText)); } });
}
function serializeGraph() {
    var nodes = [], edges = [];
    graph.getElements().forEach(function(el) {
        var cfg = el.get('config');
        if (cfg && cfg.id) nodes.push(cfg.id);
        if (el.get('subgraph')) nodes.push(el.get('subgraph'));
    });
    graph.getLinks().forEach(function(l) {
        var s = l.get('source'), t = l.get('target');
        if (s.id && t.id) edges.push([s.id, t.id]);
    });
    var flowNodes = (currentGraph && currentGraph.flowNodes) ? JSON.parse(JSON.stringify(currentGraph.flowNodes)) : {};
    var bindings = JSON.parse(JSON.stringify(graphBindings || {}));
    return {
        id: '', name: '', description: '',
        nodes: Array.from(new Set(nodes)), edges: edges,
        flowNodes: flowNodes, bindings: bindings
    };
}

// ─── Test ───────────────────────────────────────────
function openTestModal() {
    if (!$('#testInput').val().trim()) {
        $('#testInput').val(JSON.stringify({
            text: 'Aspirin may reduce the risk of heart disease. Metformin is commonly used to treat type 2 diabetes.'
        }, null, 2));
    }
    new bootstrap.Modal('#testModal').show();
}

function runTest() {
    var $o = $('#testOutput').empty();
    var graphId = current;
    if (!graphId) {
        $o.html('<p class="text-danger">Save the workflow first (workflow ID required).</p>');
        return;
    }
    var input;
    try {
        input = JSON.parse($('#testInput').val() || '{}');
    } catch (e) {
        $o.html('<p class="text-danger">Invalid JSON: ' + escHtml(e.message) + '</p>');
        return;
    }
    if (window.workflowEventSource) {
        window.workflowEventSource.close();
        window.workflowEventSource = null;
    }
    var params = new URLSearchParams({ graphId: graphId });
    Object.keys(input).forEach(function(k) { params.set(k, input[k]); });
    $o.append('<p class="text-muted wf-test-status"><i class="fas fa-spinner fa-spin me-1"></i>Running workflow <code>' + escHtml(graphId) + '</code> …</p>');
    var $runBtn = $('#runTestBtn').prop('disabled', true);
    window._wfTestGotRe = false;
    window._wfTestGotNer = false;
    window.workflowEventSource = new EventSource('/stream/test?' + params.toString());

    function markWorkflowDone(note) {
        $runBtn.prop('disabled', false);
        $o.find('.wf-test-status').remove();
        if ($o.text().indexOf(WF_COMPLETE_MSG) < 0) {
            $o.append('<hr><h6 class="text-success"><i class="fas fa-check-circle me-2"></i>' + WF_COMPLETE_MSG +
                (note ? ' <span class="text-muted small">' + escHtml(note) + '</span>' : '') + '</h6>');
        }
    }

    window.workflowEventSource.onmessage = function(e) {
        if (e.data === '[DONE]') {
            window.workflowEventSource.close();
            window.workflowEventSource = null;
            markWorkflowDone('');
            return;
        }
        var chunk = e.data.replace(/\\n/g, '\n').replace(/\$\$/g, '\n');
        if (chunk.indexOf('biomed_relation_extract') >= 0) {
            window._wfTestGotRe = true;
        }
        if (chunk.indexOf('biomed_ner') >= 0 && (chunk.indexOf('entities') >= 0 || chunk.indexOf('Chemical') >= 0)) {
            window._wfTestGotNer = true;
        }
        $o.append('<pre class="small mb-2 pb-2 border-bottom wf-test-chunk" style="white-space:pre-wrap;">' + escHtml(chunk) + '</pre>');
        $o.scrollTop($o[0].scrollHeight);
    };
    window.workflowEventSource.onerror = function() {
        if (window._wfTestGotRe) {
            markWorkflowDone('(SSE closed after RE output)');
        } else if (window._wfTestGotNer) {
            markWorkflowDone('(SSE closed after NER output)');
        } else {
            $o.append('<p class="text-warning">SSE connection interrupted. Check LLM config or retry.</p>');
            $runBtn.prop('disabled', false);
        }
        if (window.workflowEventSource) {
            window.workflowEventSource.close();
            window.workflowEventSource = null;
        }
    };
}
function createDefaultWorkflow() { renderWorkflow({ id:'default', name:'New Workflow', nodes:['START','END'], edges:[['START','END']] }); }
