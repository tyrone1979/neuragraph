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

function getGraphAgentVersions(wf) {
    wf = wf || currentGraph || {};
    return wf.agentVersions || {};
}

function getPinnedAgentVersion(agentId, wf) {
    return getGraphAgentVersions(wf)[agentId] || '';
}

function setPinnedAgentVersion(agentId, version) {
    if (!currentGraph) currentGraph = {};
    if (!currentGraph.agentVersions) currentGraph.agentVersions = {};
    if (version) currentGraph.agentVersions[agentId] = version;
    else delete currentGraph.agentVersions[agentId];
}

function _applyFlowNodeMeta(nid, f) {
    if (!agentsData[nid]) agentsData[nid] = { id: nid };
    agentsData[nid].id = nid;
    agentsData[nid].name = f.name || agentsData[nid].name || nid;
    agentsData[nid].flowKind = f.kind;
    if (f.kind === 'loop') {
        agentsData[nid].loopConfig = f.loopConfig || {};
        agentsData[nid].type = 'loop';
        agentsData[nid].flowKind = 'loop';
        if (!agentsData[nid].inputs || !agentsData[nid].inputs.length) agentsData[nid].inputs = ['input'];
        if (!agentsData[nid].outputs) agentsData[nid].outputs = { name: 'output', type: 'list' };
    } else if (f.kind === 'branch') {
        agentsData[nid].conditions = f.conditions || [];
        agentsData[nid].type = 'branch';
        agentsData[nid].flowKind = 'branch';
        if (!agentsData[nid].inputs || !agentsData[nid].inputs.length) agentsData[nid].inputs = ['input'];
        if (!agentsData[nid].outputs) agentsData[nid].outputs = { name: 'output', type: 'dict' };
    }
}

function mergeFlowNodesFromGraph(wf) {
    var fn = getGraphFlowNodes(wf);
    Object.keys(fn).forEach(function(nid) { _applyFlowNodeMeta(nid, fn[nid]); });
    graphBindings = Object.assign({}, getGraphBindings(wf));

    function mergeSubgraphMeta(subId, seen) {
        if (!subId || seen[subId]) return;
        seen[subId] = true;
        var sub = graphsById && graphsById[subId];
        if (!sub) return;
        var gfn = sub.flowNodes || {};
        Object.keys(gfn).forEach(function(nid) {
            _applyFlowNodeMeta(nid, gfn[nid]);
            var f = gfn[nid];
            if (f && f.subgraphId) mergeSubgraphMeta(f.subgraphId, seen);
        });
        Object.assign(graphBindings, sub.bindings || {});
        (sub.nodes || []).forEach(function(nid) {
            if (nid === 'START' || nid === 'END') return;
            if (graphsById && graphsById[nid]) mergeSubgraphMeta(nid, seen);
        });
    }

    var seen = {};
    Object.keys(fn).forEach(function(nid) {
        var f = fn[nid];
        if (f && f.subgraphId) mergeSubgraphMeta(f.subgraphId, seen);
    });
    (wf.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        if (agentsData[nid] && agentsData[nid].type === 'SUB') mergeSubgraphMeta(nid, seen);
        if (graphsById && graphsById[nid]) mergeSubgraphMeta(nid, seen);
    });
}

function getNodeFlowKind(nid, wf) {
    var fn = getGraphFlowNodes(wf)[nid];
    return fn ? fn.kind : null;
}

function isLoopNode(nid, wf) {
    if (getNodeFlowKind(nid, wf) === 'loop') return true;
    if (getLoopFlowMeta(nid, wf)) return true;
    var a = agentsData[nid];
    return !!(a && (a.flowKind === 'loop' || a.type === 'loop'));
}

/** Loop flow metadata from workflow or any loaded subgraph JSON. */
function getLoopFlowMeta(loopNid, wf) {
    wf = wf || currentGraph || {};
    var fn = getGraphFlowNodes(wf)[loopNid];
    if (fn && fn.kind === 'loop') return fn;
    var gid;
    for (gid in (graphsById || {})) {
        var g = graphsById[gid];
        if (!g || !g.flowNodes) continue;
        fn = g.flowNodes[loopNid];
        if (fn && fn.kind === 'loop') return fn;
    }
    return null;
}

/** Inner loops first, then outer (for expand + layout). */
function discoverNestedLoops(wf) {
    wf = wf || currentGraph || {};
    var ordered = [], seen = {};
    function walkSub(subId) {
        var sub = resolveSubgraphGraph(subId, wf);
        if (!sub) return;
        (sub.nodes || []).forEach(function(n) {
            if (n === 'START' || n === 'END') return;
            var cf = (sub.flowNodes || {})[n];
            if (cf && cf.kind === 'loop') {
                if (cf.subgraphId) walkSub(cf.subgraphId);
                if (!seen[n]) { seen[n] = true; ordered.push(n); }
            }
        });
    }
    Object.keys(getGraphFlowNodes(wf)).forEach(function(nid) {
        var f = getGraphFlowNodes(wf)[nid];
        if (f && f.kind === 'loop') {
            if (f.subgraphId) walkSub(f.subgraphId);
            if (!seen[nid]) { seen[nid] = true; ordered.push(nid); }
        }
    });
    // Also walk subgraph nodes that contain inner loops
    (wf.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        var fn = getGraphFlowNodes(wf)[nid];
        if (fn && fn.kind === 'loop') return;
        if (graphsById && graphsById[nid]) walkSub(nid);
    });
    return ordered;
}

/** Loops that are not nested inside another loop's subgraph. */
function getRootLoopIds(wf) {
    var all = discoverNestedLoops(wf);
    var nested = {};
    all.forEach(function(lid) {
        getLoopInnerIds(lid).forEach(function(nid) {
            if (isLoopNode(nid)) nested[nid] = true;
        });
    });
    return all.filter(function(lid) { return !nested[lid]; });
}

function syncFlowNodeAgents(wf) {
    wf = wf || currentGraph || {};
    (wf.nodes || []).forEach(function(nid) {
        var fn = getGraphFlowNodes(wf)[nid];
        if (fn) _applyFlowNodeMeta(nid, fn);
    });
    Object.keys(getGraphFlowNodes(wf)).forEach(function(nid) {
        _applyFlowNodeMeta(nid, getGraphFlowNodes(wf)[nid]);
    });
}

function enrichAgentMeta(nid) {
    if (getLoopFlowMeta(nid)) return;
    if (agentsData[nid] && (agentsData[nid].flowKind === 'loop' || agentsData[nid].type === 'loop')) return;
    if (!agentsData[nid] && typeof allAgents !== 'undefined') {
        var found = (allAgents || []).find(function(a) { return a && a.id === nid; });
        if (found) agentsData[nid] = JSON.parse(JSON.stringify(found));
    }
}

function findLoopAtPoint(lp) {
    var hit = null, hitArea = Infinity;
    Object.keys(subgraphRanges || {}).forEach(function(loopId) {
        if (!isLoopNode(loopId)) return;
        var el = graph.getCell(loopId);
        if (!el) return;
        var bb = el.getBBox();
        getLoopInnerIds(loopId).forEach(function(nid) {
            var inner = graph.getCell(nid);
            if (inner) bb = bb ? bb.union(inner.getBBox()) : inner.getBBox();
        });
        if (bb && lp.x >= bb.x && lp.x <= bb.x + bb.width && lp.y >= bb.y && lp.y <= bb.y + bb.height) {
            var area = bb.width * bb.height;
            if (area < hitArea) { hitArea = area; hit = loopId; }
        }
    });
    return hit;
}

function getLoopInnerIds(loopId) {
    return (subgraphRanges[loopId] && subgraphRanges[loopId].nodes) ? subgraphRanges[loopId].nodes.slice() : [];
}

function collectLoopMemberPositions(loopId, store) {
    getLoopInnerIds(loopId).forEach(function(nid) {
        var el = graph.getCell(nid);
        if (el) store[nid] = { x: el.position().x, y: el.position().y };
        if (isLoopNode(nid)) collectLoopMemberPositions(nid, store);
    });
    graph.getLinks().forEach(function(l) {
        if (l.get('parentLoop') !== loopId) return;
        var s = l.get('source'), t = l.get('target');
        if (!s || !t) return;
        [s.id, t.id].forEach(function(nid) {
            var el = graph.getCell(nid);
            if (el && !store[nid]) store[nid] = { x: el.position().x, y: el.position().y };
        });
    });
    getLoopInnerIds(loopId).forEach(function(nid) {
        if (!isLoopNode(nid)) return;
        getLoopInnerIds(nid).forEach(function(nid2) {
            var el2 = graph.getCell(nid2);
            if (el2 && !store[nid2]) store[nid2] = { x: el2.position().x, y: el2.position().y };
        });
    });
}

function isLoopInnerNode(nid) {
    var el = graph && graph.getCell(nid);
    if (el && el.get('parentLoop')) return true;
    var lid;
    for (lid in subgraphRanges) {
        if (!isLoopNode(lid)) continue;
        if ((subgraphRanges[lid].nodes || []).indexOf(nid) >= 0) return true;
    }
    return false;
}

function hasLoopInners(loopId) {
    return getLoopInnerIds(loopId).length > 0;
}

function getLoopParentId(nid) {
    var el = graph && graph.getCell(nid);
    if (el && el.get('parentLoop')) return el.get('parentLoop');
    var lid;
    for (lid in subgraphRanges) {
        if (!isLoopNode(lid)) continue;
        if ((subgraphRanges[lid].nodes || []).indexOf(nid) >= 0) return lid;
    }
    return null;
}

function getLoopInnerEdges(loopId) {
    var info = subgraphRanges[loopId];
    if (info && info.edges && info.edges.length) return info.edges.slice();
    var fn = getGraphFlowNodes()[loopId];
    var sub = null;
    if (fn && fn.subgraphId) sub = resolveSubgraphGraph(fn.subgraphId);
    if (!sub) sub = resolveSubgraphGraph(loopId);
    if (!sub || !sub.edges) return [];
    return sub.edges.filter(function(e) { return e[0] !== 'START' && e[1] !== 'END'; });
}

function resolveSelectionElement(el) {
    if (!el || !el.isElement || !el.isElement()) return el;
    var pl = el.get('parentLoop');
    if (pl && isLoopNode(pl)) {
        var loopEl = graph.getCell(pl);
        if (loopEl) return loopEl;
    }
    return el;
}

function getLinkParentLoop(link) {
    var pl = link.get('parentLoop');
    if (pl && isLoopNode(pl)) return pl;
    var s = link.get('source'), t = link.get('target');
    if (!s || !t || !s.id || !t.id) return null;
    if (!isLoopInnerNode(s.id) || !isLoopInnerNode(t.id)) return null;
    var lid;
    for (lid in subgraphRanges) {
        if (!isLoopNode(lid)) continue;
        var nodes = subgraphRanges[lid].nodes || [];
        if (nodes.indexOf(s.id) >= 0 && nodes.indexOf(t.id) >= 0) return lid;
    }
    return null;
}

function getLoopInnerDisplayNodes(loopId) {
    return getLoopInnerIds(loopId).map(function(nid) {
        enrichAgentMeta(nid);
        var a = agentsData[nid] || { id: nid, name: nid, type: 'LLM' };
        var t = a.type || 'LLM';
        if (a.flowKind === 'loop' || t === 'loop') t = 'loop';
        return { id: nid, name: a.name || nid, type: t };
    });
}

function buildLoopInnerBodyHtml(loopId) {
    var children = getLoopInnerDisplayNodes(loopId);
    if (!children.length) {
        return '<div class="wf-loop-empty">Drop agents or subgraphs here</div>';
    }
    var html = '<div class="wf-loop-inner">';
    children.forEach(function(ch) {
        var dt = ch.type === 'loop' ? 'loop' : ch.type;
        var stroke = getNodeStroke(dt, false);
        var letter = typeIconLetters[dt] || typeIconLetters[ch.type] || ch.type.charAt(0) || '?';
        var label = typeLabels[dt] || typeLabels[ch.type] || ch.type;
        html += '<div class="wf-loop-child">';
        html += '<span class="wf-loop-child-icon" style="background:' + escHtml(stroke) + '">' + escHtml(letter) + '</span>';
        html += '<span class="wf-loop-child-body">';
        html += '<span class="wf-loop-child-name" title="' + escHtml(ch.name) + '">' + escHtml(truncateText(ch.name, 28)) + '</span>';
        html += '<span class="wf-loop-child-type">' + escHtml(label) + '</span>';
        html += '</span></div>';
    });
    html += '</div>';
    return html;
}

function buildCompoundLoopLayout(id, agent, stroke, flowKind) {
    var name = truncateText((agent && agent.name) || id, 32);
    var inputs = normalizeInputs(agent);
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : 'output';
    var lc = (agent && agent.loopConfig) || {};
    var loopType = lc.loopType || 'foreach';
    var innerChildren = getLoopInnerDisplayNodes(id);
    var innerCount = innerChildren.length;
    var width = Math.max(WF_NODE_WIDTH, 300);
    var innerBlockH = innerCount ? (innerCount * 48 + 16) : 40;
    var bodyH = 8 + 18 + innerBlockH + 8 + WF_SECTION_LABEL_H + WF_ROW_H + WF_SECTION_LABEL_H + WF_ROW_H + WF_BODY_PAD;
    var height = WF_HEADER_H + bodyH;
    var portItems = [
        { id: 'in_default', group: 'in', args: { y: portYPercent(height / 2, height) } },
        { id: 'out_' + outName, group: 'out', args: { y: portYPercent(height / 2, height) } }
    ];
    var html = '<div class="wf-node wf-node--loop" xmlns="' + escHtml('http://www.w3.org/1999/xhtml') + '">';
    html += '<div class="wf-node-header" style="background:' + escHtml(stroke) + '">';
    html += '<span class="wf-node-icon">↻</span>';
    html += '<span class="wf-node-title" title="' + escHtml((agent && agent.name) || id) + '">' + escHtml(name) + '</span>';
    html += '<span class="wf-node-type" title="loop">Loop</span>';
    html += '</div><div class="wf-node-body">';
    html += '<div class="wf-loop-meta">Loop: ' + escHtml(loopType) + '</div>';
    html += buildLoopInnerBodyHtml(id);
    html += '<div class="wf-io-block wf-io-block--compact"><div class="wf-io-label">INPUT</div>';
    if (inputs.length) {
        inputs.forEach(function(inp) {
            html += '<div class="wf-io-row"><span class="wf-io-dot wf-io-dot--in"></span>';
            html += '<span class="wf-io-name">' + escHtml(truncateText(inp, 22)) + '</span></div>';
        });
    } else {
        html += '<div class="wf-io-empty">input</div>';
    }
    html += '</div>';
    html += '<div class="wf-io-block wf-io-block--compact"><div class="wf-io-label">OUTPUT</div>';
    html += '<div class="wf-io-row"><span class="wf-io-dot wf-io-dot--out"></span>';
    html += '<span class="wf-io-name">' + escHtml(truncateText(outName, 20)) + '</span></div>';
    html += '</div></div></div>';
    return {
        width: width, height: height, html: html, stroke: stroke,
        portItems: portItems,
        config: {
            id: id, name: (agent && agent.name) || id,
            inputs: inputs,
            outputs: agent ? agent.outputs : { name: 'output', type: 'list' },
            type: 'loop', flowKind: flowKind || 'loop',
            loopConfig: lc,
            innerNodes: innerChildren.map(function(c) { return c.id; }),
            conditions: []
        }
    };
}

function estimateLoopRegionSize(loopId) {
    var innerIds = getLoopInnerIds(loopId);
    if (!innerIds.length) return { width: 320, height: 180 };
    var gap = 56;
    var totalW = 0;
    var maxH = 0;
    innerIds.forEach(function(nid) {
        var w = WF_NODE_WIDTH;
        var h = 140;
        if (isLoopNode(nid) && hasLoopInners(nid)) {
            var nested = estimateLoopRegionSize(nid);
            w = nested.width;
            h = nested.height;
        } else {
            enrichAgentMeta(nid);
            var agent = agentsData[nid] || {};
            var dt = agent.flowKind || agent.type || 'LLM';
            var metrics = computeWfNodeMetrics(agent, dt, agent.type || 'LLM');
            h = metrics.height;
        }
        totalW += w + gap;
        maxH = Math.max(maxH, h);
    });
    return {
        width: Math.max(320, totalW + LOOP_PAD * 2),
        height: Math.max(180, maxH + LOOP_HEADER_H + LOOP_PAD + LOOP_BOTTOM_EXTRA)
    };
}

function bboxIntersects(a, b, margin) {
    margin = margin || 0;
    return !(a.x + a.width + margin < b.x || b.x + b.width + margin < a.x ||
        a.y + a.height + margin < b.y || b.y + b.height + margin < a.y);
}

function isTopLevelCanvasNode(el) {
    if (!el || !el.isElement || !el.isElement()) return false;
    var id = el.id;
    if (!id || id === 'START' || id === 'END') return false;
    if (String(id).indexOf('_container') >= 0) return false;
    if (el.get('subgraph') || el.get('parentLoop')) return false;
    if (isLoopInnerNode(id)) return false;
    return true;
}

/** Push top-level nodes away from loop shells after inner layout expands bounds. */
function resolveLoopTopLevelOverlaps() {
    if (!graph) return;
    var loopIds = discoverNestedLoops(currentGraph || {}).slice().reverse();
    var gap = 56;
    for (var pass = 0; pass < 2; pass++) {
    loopIds.forEach(function(loopId) {
        var loopEl = graph.getCell(loopId);
        if (!loopEl || !loopEl.get('isLoopShell')) return;
        var loopBox = loopEl.getBBox();
        var avoid = {
            x: loopBox.x - gap,
            y: loopBox.y - gap,
            width: loopBox.width + gap * 2,
            height: loopBox.height + gap * 2
        };
        graph.getElements().forEach(function(el) {
            if (!isTopLevelCanvasNode(el)) return;
            if (el.id === loopId) return;
            var bb = el.getBBox();
            if (!bboxIntersects(avoid, bb, 8)) return;
            var shiftX = (avoid.x + avoid.width + gap) - bb.x;
            if (shiftX > 0) {
                el.position(bb.x + shiftX, bb.y);
                bb = el.getBBox();
            }
            if (bboxIntersects(avoid, bb, 8)) {
                var shiftY = (avoid.y + avoid.height + gap) - bb.y;
                if (shiftY > 0) el.position(bb.x, bb.y + shiftY);
            }
        });
    });
    }
}

function createLoopShell(loopId, agent, size) {
    agent = agent || agentsData[loopId] || { id: loopId, name: loopId, type: 'loop', flowKind: 'loop' };
    var stroke = nodeStyles.loop.stroke;
    var name = (agent.name || loopId);
    var outName = (agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : 'output';
    var lc = agent.loopConfig || {};
    var loopType = lc.loopType || 'foreach';
    var label = name + '\n↻ Loop · ' + loopType;
    var w = (size && size.width) ? size.width : 320;
    var h = (size && size.height) ? size.height : 180;
    return new joint.shapes.standard.Rectangle({
        id: loopId,
        isLoopShell: true,
        size: { width: w, height: h },
        attrs: {
            body: {
                fill: 'rgba(59,130,246,0.07)',
                stroke: stroke,
                strokeWidth: 1.5,
                rx: 12,
                ry: 12
            },
            label: {
                text: label,
                fill: '#1e40af',
                fontSize: 12,
                fontWeight: 'bold',
                refX: 14,
                refY: 12,
                textAnchor: 'start',
                textVerticalAnchor: 'top',
                textWrap: { width: w - 28, maxLineCount: 3 }
            }
        },
        ports: {
            groups: {
                in: {
                    position: { name: 'left' },
                    attrs: { circle: { r: 6, magnet: true, fill: '#fff', stroke: stroke, strokeWidth: 2 } }
                },
                out: {
                    position: { name: 'right' },
                    attrs: { circle: { r: 6, magnet: true, fill: '#fff', stroke: stroke, strokeWidth: 2 } }
                }
            },
            items: [
                { id: 'in_default', group: 'in' },
                { id: 'out_' + outName, group: 'out' }
            ]
        },
        config: {
            id: loopId,
            name: name,
            type: 'loop',
            flowKind: 'loop',
            inputs: agent.inputs || ['input'],
            outputs: agent.outputs || { name: 'output', type: 'list' },
            loopConfig: lc,
            subgraphId: agent.subgraphId
        }
    });
}

function ensureLoopShell(loopId) {
    var el = graph.getCell(loopId);
    if (!el || !hasLoopInners(loopId)) return el;
    if (el.get('isLoopShell')) return el;
    var pos = el.position();
    var cfg = el.get('config') || agentsData[loopId];
    el.remove();
    var shell = createLoopShell(loopId, cfg);
    shell.position(pos.x, pos.y);
    graph.addCell(shell);
    return shell;
}

function orderNodesHorizontal(ids, edges) {
    if (!ids || !ids.length) return [];
    var edgeList = edges || [];
    var order = [], seen = {}, queue = [];
    ids.forEach(function(nid) {
        var hasPred = edgeList.some(function(e) {
            return e[1] === nid && ids.indexOf(e[0]) >= 0;
        });
        if (!hasPred) queue.push(nid);
    });
    if (!queue.length) queue.push(ids[0]);
    while (queue.length) {
        var nid = queue.shift();
        if (seen[nid]) continue;
        seen[nid] = true;
        order.push(nid);
        edgeList.forEach(function(e) {
            if (e[0] === nid && ids.indexOf(e[1]) >= 0 && !seen[e[1]]) queue.push(e[1]);
        });
    }
    ids.forEach(function(nid) { if (!seen[nid]) order.push(nid); });
    return order;
}

function computeInnerLayoutPositions(loopId) {
    var innerIds = getLoopInnerIds(loopId);
    var edges = getLoopInnerEdges(loopId).filter(function(e) {
        return innerIds.indexOf(e[0]) >= 0 && innerIds.indexOf(e[1]) >= 0;
    });
    var ordered = orderNodesHorizontal(innerIds, edges);
    var positions = {}, x = 0, gap = 56;
    ordered.forEach(function(nid) {
        var el = graph.getCell(nid);
        var w = el ? el.size().width : WF_NODE_WIDTH;
        positions[nid] = { x: x, y: 0 };
        x += w + gap;
    });
    return positions;
}

function filterInnerEdges(edges) {
    return (edges || []).filter(function(e) {
        return e[0] !== 'START' && e[1] !== 'END';
    });
}

function addInnerGraphLinks(nodeIds, edges, opts) {
    opts = opts || {};
    filterInnerEdges(edges).forEach(function(e) {
        if (nodeIds.indexOf(e[0]) < 0 || nodeIds.indexOf(e[1]) < 0) return;
        var exists = graph.getLinks().some(function(l) {
            var s = l.get('source'), t = l.get('target');
            return s && t && s.id === e[0] && t.id === e[1];
        });
        if (exists) return;
        var link = createLink(e[0], e[1]);
        if (opts.parentLoop) {
            link.set('parentLoop', opts.parentLoop);
            link.set('z', 1);
        }
        graph.addCell(link);
    });
}

function collectSubgraphMemberPositions(subId) {
    var positions = { nodes: {}, containers: {} };
    var info = subgraphRanges[subId];
    if (!info) return positions;
    (info.nodes || []).forEach(function(nid) {
        var el = graph.getCell(nid);
        if (!el) return;
        if (!el.get('parentLoop')) positions.nodes[nid] = el.position();
        // Include loop shell position
        if (isLoopNode(nid) && hasLoopInners(nid)) {
            var shell = graph.getCell(nid);
            if (shell) positions.nodes[nid] = shell.position();
            // Also collect all inner nodes of the loop so they move with the subgraph
            getLoopInnerIds(nid).forEach(function(innerId) {
                var inner = graph.getCell(innerId);
                if (inner) positions.nodes[innerId] = inner.position();
            });
        }
    });
    (info.subgraphs || []).forEach(function(childId) {
        var cnt = graph.getCell(childId + '_container');
        if (cnt) positions.containers[childId] = cnt.position();
        var nested = collectSubgraphMemberPositions(childId);
        Object.keys(nested.nodes).forEach(function(k) { positions.nodes[k] = nested.nodes[k]; });
        Object.keys(nested.containers).forEach(function(k) { positions.containers[k] = nested.containers[k]; });
    });
    return positions;
}

function applySubgraphDragDelta(state, dx, dy) {
    Object.keys(state.members.nodes).forEach(function(nid) {
        var el = graph.getCell(nid);
        var p0 = state.members.nodes[nid];
        if (el && p0) el.position(p0.x + dx, p0.y + dy);
    });
    Object.keys(state.members.containers).forEach(function(cid) {
        var cnt = graph.getCell(cid + '_container');
        var p0 = state.members.containers[cid];
        if (cnt && p0) cnt.position(p0.x + dx, p0.y + dy);
    });
}

/** Create loop shells and inner nodes/links without final shell placement. */
function prepareLoopInnerContent(loopId) {
    if (!graph || !isLoopNode(loopId) || !hasLoopInners(loopId)) return;

    var innerIds = getLoopInnerIds(loopId);
    innerIds.forEach(function(nid) {
        if (isLoopNode(nid) && hasLoopInners(nid)) prepareLoopInnerContent(nid);
    });

    ensureLoopShell(loopId);
    innerIds.forEach(function(nid) {
        enrichAgentMeta(nid);
        if (isLoopNode(nid)) {
            var meta = getLoopFlowMeta(nid) || {};
            agentsData[nid] = agentsData[nid] || { id: nid };
            agentsData[nid].type = 'loop';
            agentsData[nid].flowKind = 'loop';
            agentsData[nid].name = meta.name || agentsData[nid].name || nid;
            agentsData[nid].loopConfig = meta.loopConfig || agentsData[nid].loopConfig || {};
            if (meta.subgraphId) agentsData[nid].subgraphId = meta.subgraphId;
        }
        var el = graph.getCell(nid);
        if (!el) {
            el = createNode(nid);
            graph.addCell(el);
        } else if (isLoopNode(nid) && hasLoopInners(nid) && !el.get('isLoopShell')) {
            var pos = el.position();
            el.remove();
            el = ensureLoopShell(nid);
            el.position(pos.x, pos.y);
            graph.addCell(el);
        }
        el.set('parentLoop', loopId);
        el.set('z', 10);
    });
    addInnerGraphLinks(innerIds, getLoopInnerEdges(loopId), { parentLoop: loopId });
}

function repositionLoopChildren(loopId) {
    var loopEl = graph.getCell(loopId);
    if (!loopEl) return;
    var lp = loopEl.position();
    var relPos = computeInnerLayoutPositions(loopId);
    getLoopInnerIds(loopId).forEach(function(nid) {
        var el = graph.getCell(nid);
        if (!el) return;
        var rel = relPos[nid] || { x: 0, y: 0 };
        el.position(lp.x + LOOP_PAD + rel.x, lp.y + LOOP_HEADER_H + LOOP_PAD + rel.y);
        if (isLoopNode(nid) && hasLoopInners(nid)) {
            fitLoopShellToContent(nid, { anchor: true, skipReposition: true });
            repositionLoopChildren(nid);
        }
    });
}

function layoutLoopRegion(loopId) {
    if (!graph || !isLoopNode(loopId)) return;
    if (!hasLoopInners(loopId)) {
        _refreshLoopVisual(loopId);
        return;
    }

    prepareLoopInnerContent(loopId);

    var loopEl = graph.getCell(loopId);
    if (!loopEl) return;
    loopEl.set('z', 1);

    repositionLoopChildren(loopId);
    var anchorShell = !!loopEl.get('parentLoop');
    fitLoopShellToContent(loopId, { anchor: anchorShell, skipReposition: true });
    repositionLoopChildren(loopId);

    graph.getLinks().forEach(function(l) {
        if (l.get('parentLoop') === loopId) l.set('z', 8);
    });
    reattachLinkPorts();
    rerouteAllLinks();
}

function isLoopShellInsideParent(loopId) {
    var el = graph.getCell(loopId);
    var parentId = el && el.get('parentLoop');
    if (!el || !parentId) return true;
    var parent = graph.getCell(parentId);
    if (!parent) return true;
    var ib = el.getBBox();
    var pb = parent.getBBox();
    var pad = 4;
    return ib.x >= pb.x - pad && ib.y >= pb.y - pad
        && (ib.x + ib.width) <= (pb.x + pb.width + pad)
        && (ib.y + ib.height) <= (pb.y + pb.height + pad);
}

/** Re-layout nested loop shells that drifted outside their parent bounds. */
function syncNestedLoopShellPositions() {
    if (!graph) return;
    discoverNestedLoops(currentGraph || {}).forEach(function(loopId) {
        var el = graph.getCell(loopId);
        if (!el || !el.get('isLoopShell') || !el.get('parentLoop')) return;
        if (isLoopShellInsideParent(loopId)) return;
        var parentId = el.get('parentLoop');
        repositionLoopChildren(parentId);
        fitLoopShellToContent(loopId, { anchor: true, skipReposition: true });
        repositionLoopChildren(loopId);
    });
}

function finalizeLoopLayout(wf) {
    getRootLoopIds(wf || currentGraph || {}).forEach(function(lid) {
        fitLoopShellToContent(lid, { anchor: false, skipReposition: true });
        repositionLoopChildren(lid);
    });
}

/** Resolve nested graph JSON for a loop node id or subgraph id. */
function resolveSubgraphGraph(subId, wf) {
    wf = wf || currentGraph || {};
    if (graphsById && graphsById[subId]) return graphsById[subId];
    var fn = getGraphFlowNodes(wf)[subId];
    if (fn && fn.subgraphId && graphsById && graphsById[fn.subgraphId]) return graphsById[fn.subgraphId];
    if (wf.visualData && wf.visualData.nodes) {
        var vn = wf.visualData.nodes.find(function(n) { return n.id === subId || n.originalId === subId; });
        if (vn && vn.data) return vn.data;
    }
    return null;
}

/** Topology read from JointJS canvas (WYSIWYG). */
function extractCanvasTopology() {
    if (!graph || typeof graph.getElements !== 'function') {
        return { nodes: [], edges: [] };
    }
    var ids = [];
    graph.getElements().forEach(function(el) {
        var id = el.id;
        if (!id || id.indexOf('_container') >= 0 || el.get('subgraph')) return;
        if (el.get('parentLoop') || isLoopInnerNode(id)) return;
        ids.push(id);
    });
    var mid = ids.filter(function(id) { return id !== 'START' && id !== 'END'; }).sort();
    var nodes = [];
    if (ids.indexOf('START') >= 0) nodes.push('START');
    nodes = nodes.concat(mid);
    if (ids.indexOf('END') >= 0) nodes.push('END');
    var edges = [];
    graph.getLinks().forEach(function(link) {
        var s = link.get('source'), t = link.get('target');
        if (!s || !s.id || !t || !t.id) return;
        if (link.get('parentLoop') || isLoopInnerNode(s.id) || isLoopInnerNode(t.id)) return;
        edges.push([s.id, t.id]);
    });
    return { nodes: nodes, edges: edges };
}

function syncCurrentGraphFromCanvas() {
    if (!currentGraph) currentGraph = {};
    var topo = extractCanvasTopology();
    if (topo.nodes && topo.nodes.length) currentGraph.nodes = topo.nodes;
    if (topo.edges && topo.edges.length) currentGraph.edges = topo.edges;
}

/** Snapshot every element position from the live canvas (for save + layout restore). */
function collectCanvasLayoutPositions() {
    var positions = {};
    if (!graph) return positions;
    graph.getElements().forEach(function(el) {
        var p = el.position();
        positions[el.id] = { x: p.x, y: p.y };
    });
    return positions;
}

/** Restore a previously saved manual layout; returns true when any node was placed. */
function applyCanvasLayoutPositions(positions) {
    if (!positions || !graph) return false;
    var applied = false;
    Object.keys(positions).forEach(function(id) {
        var pos = positions[id];
        var el = graph.getCell(id);
        if (!el || !pos || typeof pos.x !== 'number' || typeof pos.y !== 'number') return;
        el.position(pos.x, pos.y);
        applied = true;
    });
    if (applied) {
        reattachLinkPorts();
        updateSubgraphContainerPositions();
    }
    return applied;
}

function persistCanvasLayoutToGraph(wf) {
    wf = wf || currentGraph || {};
    getRootLoopIds(wf).forEach(function(lid) {
        if (hasLoopInners(lid) && graph.getCell(lid)) layoutLoopRegion(lid);
    });
    wf.visualData = wf.visualData || {};
    wf.visualData.layout = collectCanvasLayoutPositions();
    if (currentGraph) currentGraph.visualData = wf.visualData;
    return wf.visualData.layout;
}

let availableLLMs = [];
let agentVersionCache = {};

const nodeStyles = {
    startEnd: { stroke: '#17a2b8' }, PGM: { stroke: '#28a745' },
    LLM: { stroke: '#4b6cb7' }, SUB: { stroke: '#764ba2' },
    branch: { stroke: '#f59e0b' }, loop: { stroke: '#3b82f6' }, tool: { stroke: '#ec4899' }
};
const typeIcons = { PGM:'fa-cog',LLM:'fa-robot',SUB:'fa-project-diagram',branch:'fa-code-branch',loop:'fa-redo',tool:'fa-wrench',flow:'fa-arrow-right' };
const typeLabels = { PGM:'Code', LLM:'LLM', SUB:'Subgraph', branch:'IF/ELSE', loop:'Loop', tool:'Tool', flow:'Flow' };
const typeIconLetters = { PGM:'C', LLM:'L', SUB:'S', branch:'?', loop:'↻', tool:'T', flow:'▶' };

const BRANCH_OPS = [
    { id: 'not_empty', label: 'Is not empty', needsValue: false },
    { id: 'empty', label: 'Is empty', needsValue: false },
    { id: 'exists', label: 'Exists (truthy)', needsValue: false },
    { id: 'not_exists', label: 'Not exists', needsValue: false },
    { id: 'eq', label: 'Equals', needsValue: true },
    { id: 'ne', label: 'Not equals', needsValue: true },
    { id: 'contains', label: 'Contains', needsValue: true },
    { id: 'not_contains', label: 'Does not contain', needsValue: true },
    { id: 'gt', label: 'Greater than', needsValue: true },
    { id: 'gte', label: 'Greater or equal', needsValue: true },
    { id: 'lt', label: 'Less than', needsValue: true },
    { id: 'lte', label: 'Less or equal', needsValue: true }
];

const COMMON_STATE_FIELDS = ['text', 'entities', 'relations', 'route', 'output'];

function normalizeBranchCondition(c) {
    if (!c || typeof c !== 'object') return { label: 'Branch', field: '', op: 'not_empty', value: '' };
    if (c.field || c.op) return {
        label: c.label || 'Branch',
        field: c.field || '',
        op: c.op || 'not_empty',
        value: c.value != null ? String(c.value) : ''
    };
    var expr = (c.condition || '').trim();
    if (expr.startsWith('!')) {
        return { label: c.label || 'False', field: expr.slice(1).trim(), op: 'empty', value: '' };
    }
    return { label: c.label || 'True', field: expr, op: 'not_empty', value: '' };
}

function persistFlowNode(nid) {
    if (!currentGraph) currentGraph = {};
    if (!currentGraph.flowNodes) currentGraph.flowNodes = {};
    var cfg = agentsData[nid] || {};
    var kind = cfg.flowKind || (cfg.type === 'loop' ? 'loop' : (cfg.type === 'branch' ? 'branch' : null));
    if (!kind) return;
    var entry = { kind: kind, name: cfg.name || nid };
    if (kind === 'branch') entry.conditions = (cfg.conditions || []).map(normalizeBranchCondition);
    if (kind === 'loop') {
        entry.loopConfig = cfg.loopConfig || {};
        entry.subgraphId = cfg.subgraphId || nid;
    }
    currentGraph.flowNodes[nid] = entry;
}

function collectUpstreamFieldOptions(nodeId) {
    var opts = [{ value: '', label: '-- Select source --' }];
    var seen = {};
    function add(val, label) {
        if (!val || seen[val]) return;
        seen[val] = true;
        opts.push({ value: val, label: label });
    }
    getUpstreamNodeIds(nodeId).forEach(function(uid) {
        var cell = graph.getCell(uid);
        var cfg = cell && cell.get('config');
        if (!cfg) return;
        var outName = (cfg.outputs && cfg.outputs.name) ? cfg.outputs.name : 'output';
        (cfg.inputs || []).forEach(function(inp) {
            add('{{ ' + uid + '.' + inp + ' }}', uid + ' · ' + inp);
        });
        add('{{ ' + uid + '.' + outName + ' }}', uid + ' · ' + outName + ' (out)');
        COMMON_STATE_FIELDS.forEach(function(f) {
            add('{{ ' + uid + '.' + f + ' }}', uid + ' · ' + f);
        });
    });
    add('{{ text }}', 'workflow · text');
    return opts;
}

function buildFieldSelectHtml(nodeId, selectedField, cls) {
    var opts = collectUpstreamFieldOptions(nodeId);
    var fields = [{ value: '', label: '-- field --' }];
    var seenF = {};
    opts.forEach(function(o) {
        var m = o.value.match(/\{\{\s*([^.]+)\.([^}\s]+)\s*\}\}/);
        if (m && !seenF[m[2]]) {
            seenF[m[2]] = true;
            fields.push({ value: m[2], label: m[1] + '.' + m[2] });
        }
    });
    COMMON_STATE_FIELDS.forEach(function(f) {
        if (!seenF[f]) fields.push({ value: f, label: f });
    });
    var html = '<select class="form-select form-select-sm ' + cls + '">';
    fields.forEach(function(f) {
        html += '<option value="' + escHtml(f.value) + '"' + (f.value === selectedField ? ' selected' : '') + '>' + escHtml(f.label) + '</option>';
    });
    html += '</select>';
    return html;
}

function buildMappingSelectHtml(nodeId, currentVal) {
    var opts = collectUpstreamFieldOptions(nodeId);
    var html = '<select class="form-select form-select-sm mapping-select flex-grow-1">';
    var matched = false;
    opts.forEach(function(o) {
        var sel = (currentVal === o.value) ? ' selected' : '';
        if (sel) matched = true;
        html += '<option value="' + escHtml(o.value) + '"' + sel + '>' + escHtml(o.label) + '</option>';
    });
    if (currentVal && !matched) {
        html += '<option value="' + escHtml(currentVal) + '" selected>' + escHtml(currentVal) + ' (custom)</option>';
    }
    html += '</select>';
    return html;
}

function collectSubgraphInputFields(subgraphId) {
    var sub = resolveSubgraphGraph(subgraphId);
    if (!sub) return [];
    var seen = {}, fields = [];
    function add(f) {
        if (!f || seen[f]) return;
        seen[f] = true;
        fields.push(f);
    }
    (sub.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        var a = agentsData[nid];
        if (a && a.inputs) a.inputs.forEach(add);
        var binds = (sub.bindings || {})[nid];
        if (binds) Object.keys(binds).forEach(add);
    });
    return fields;
}

function buildLoopItemBindingSelectHtml(currentVal, loopNid) {
    var opts = [{ value: '', label: '-- expression --' }];
    var meta = loopNid ? getLoopFlowMeta(loopNid) : null;
    var subId = (meta && meta.subgraphId) || (loopNid && agentsData[loopNid] && agentsData[loopNid].subgraphId);
    var seen = {};
    function addOpt(value, label) {
        if (!value || seen[value]) return;
        seen[value] = true;
        opts.push({ value: value, label: label });
    }
    if (loopNid) {
        collectUpstreamFieldOptions(loopNid).forEach(function(o) { addOpt(o.value, o.label); });
    }
    collectSubgraphInputFields(subId).forEach(function(f) {
        addOpt('{{ ' + f + ' }}', 'item · ' + f);
    });
    addOpt('{{ item }}', 'item · raw');
    var html = '<select class="form-select form-select-sm loop-item-binding-select flex-grow-1">';
    var matched = false;
    opts.forEach(function(o) {
        var sel = (currentVal === o.value) ? ' selected' : '';
        if (sel) matched = true;
        html += '<option value="' + escHtml(o.value) + '"' + sel + '>' + escHtml(o.label) + '</option>';
    });
    if (currentVal && !matched) {
        html += '<option value="' + escHtml(currentVal) + '" selected>' + escHtml(currentVal) + ' (custom)</option>';
    }
    html += '</select>';
    return html;
}

function updateLoopConfigVisibility(loopType) {
    var t = loopType || 'foreach';
    $('#forLoopConfig').toggleClass('d-none', t !== 'for');
    $('#whileLoopConfig').toggleClass('d-none', t !== 'while');
    $('#foreachLoopConfig').toggleClass('d-none', t !== 'foreach');
}

function syncLoopPanelToAgent(loopNid) {
    if (!loopNid || !agentsData[loopNid]) return;
    var lc = agentsData[loopNid].loopConfig || {};
    if ($('#loopType').length) lc.loopType = $('#loopType').val() || lc.loopType || 'foreach';
    if ($('#loopArray').length) lc.array = $('#loopArray').val() || lc.array || '';
    if ($('#loopCount').length) lc.count = parseInt($('#loopCount').val(), 10) || lc.count || 10;
    agentsData[loopNid].loopConfig = lc;
    persistFlowNode(loopNid);
}

function renderLoopItemBindings(loopNid) {
    var meta = getLoopFlowMeta(loopNid);
    var subId = (meta && meta.subgraphId) || (agentsData[loopNid] && agentsData[loopNid].subgraphId);
    var lc = (agentsData[loopNid] && agentsData[loopNid].loopConfig) || {};
    var fields = collectSubgraphInputFields(subId);
    var ib = lc.itemBindings || {};
    var $sec = $('#loopItemBindingsSection');
    var $box = $('#loopItemBindings').empty();
    if (!subId || !fields.length) {
        $sec.addClass('d-none');
        return;
    }
    $sec.removeClass('d-none');
    fields.forEach(function(field) {
        var val = ib[field] || '{{ ' + field + ' }}';
        $box.append(
            '<div class="d-flex align-items-center mb-2 loop-item-binding-row" data-field="' + escHtml(field) + '">' +
            '<span class="badge bg-secondary me-2" style="min-width:60px">' + escHtml(field) + '</span>' +
            buildLoopItemBindingSelectHtml(val, loopNid) +
            '</div>'
        );
    });
    $('.loop-item-binding-select').off('change').on('change', function() {
        var row = $(this).closest('.loop-item-binding-row');
        var field = row.data('field');
        if (!agentsData[loopNid].loopConfig) agentsData[loopNid].loopConfig = {};
        if (!agentsData[loopNid].loopConfig.itemBindings) agentsData[loopNid].loopConfig.itemBindings = {};
        var v = $(this).val();
        if (v) agentsData[loopNid].loopConfig.itemBindings[field] = v;
        else delete agentsData[loopNid].loopConfig.itemBindings[field];
        persistFlowNode(loopNid);
    });
}

const WF_NODE_WIDTH = 268;
const ZOOM_MIN = 0.2;
const ZOOM_MAX = 3;
const ZOOM_BTN_STEP = 0.2;
const ZOOM_WHEEL_STEP = 0.08;
const WF_HEADER_H = 40;
const LOOP_HEADER_H = 52;
const LOOP_PAD = 24;
const LOOP_BOTTOM_EXTRA = 20;
const WF_BODY_PAD_TOP = 10;
const WF_BODY_PAD_BOTTOM = 12;
const WF_IO_LABEL_H = 14;
const WF_IO_BLOCK_GAP = 6;
const WF_META_LINE_H = 28;
const WF_ID_ROW_H = 20;
const WF_ROW_H = 26;
const WF_SECTION_LABEL_H = WF_IO_LABEL_H;
const WF_BODY_PAD = WF_BODY_PAD_TOP;

const LINK_ROUTE_PAD = 28;
const LINK_PORT_CORRIDOR = LINK_ROUTE_PAD + 18;
const LINK_PORT_OFFSET = 0;
const LINK_BOUNDARY_OFFSET = 5;
var _routeObstacleElements = null;

function expandRect(bb, pad) {
    return {
        x: bb.x - pad,
        y: bb.y - pad,
        width: bb.width + pad * 2,
        height: bb.height + pad * 2
    };
}

function pointInRect(p, r) {
    return p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height;
}

function isInsideStrictInterior(point, bb, inset) {
    inset = inset == null ? 2 : inset;
    return point.x > bb.x + inset && point.x < bb.x + bb.width - inset &&
        point.y > bb.y + inset && point.y < bb.y + bb.height - inset;
}

function isPortCorridor(point, bb, side, pad) {
    pad = pad == null ? LINK_ROUTE_PAD : pad;
    var depth = LINK_PORT_CORRIDOR;
    if (side === 'right') {
        return point.x >= bb.x + bb.width - 2 && point.x <= bb.x + bb.width + depth &&
            point.y >= bb.y - pad && point.y <= bb.y + bb.height + pad;
    }
    if (side === 'left') {
        return point.x >= bb.x - depth && point.x <= bb.x + 2 &&
            point.y >= bb.y - pad && point.y <= bb.y + bb.height + pad;
    }
    if (side === 'bottom') {
        return point.y >= bb.y + bb.height - 2 && point.y <= bb.y + bb.height + depth &&
            point.x >= bb.x - pad && point.x <= bb.x + bb.width + pad;
    }
    if (side === 'top') {
        return point.y >= bb.y - depth && point.y <= bb.y + 2 &&
            point.x >= bb.x - pad && point.x <= bb.x + bb.width + pad;
    }
    return false;
}

function isEndpointCorridor(point, bb, role) {
    if (role === 'source') return isPortCorridor(point, bb, 'right');
    if (role === 'target') return isPortCorridor(point, bb, 'left');
    return false;
}

function isNodeInSubgraph(nid, subId) {
    var info = subgraphRanges[subId];
    if (!info || !nid) return false;
    if ((info.nodes || []).indexOf(nid) >= 0) return true;
    if ((info.subgraphs || []).indexOf(nid) >= 0) return true;
    if (isLoopInnerNode(nid)) {
        var lp = getLoopParentId(nid);
        if (lp && (info.nodes || []).indexOf(lp) >= 0) return true;
    }
    var i;
    for (i = 0; i < (info.subgraphs || []).length; i++) {
        if (isNodeInSubgraph(nid, info.subgraphs[i])) return true;
    }
    return false;
}

function areBothInSubgraph(aId, bId, subId) {
    return isNodeInSubgraph(aId, subId) && isNodeInSubgraph(bId, subId);
}

function isNodeInLoop(nid, loopId) {
    if (!nid || !loopId) return false;
    if (nid === loopId) return true;
    return getLoopParentId(nid) === loopId;
}

function areBothInLoop(aId, bId, loopId) {
    return isNodeInLoop(aId, loopId) && isNodeInLoop(bId, loopId);
}

function linkCrossesLoopBoundary(link, loopId) {
    var src = link.get('source'), tgt = link.get('target');
    if (!src || !tgt || !src.id || !tgt.id) return false;
    return isNodeInLoop(src.id, loopId) !== isNodeInLoop(tgt.id, loopId);
}

function linkCrossesSubgraphBoundary(link, subId) {
    var src = link.get('source'), tgt = link.get('target');
    if (!src || !tgt || !src.id || !tgt.id) return false;
    return isNodeInSubgraph(src.id, subId) !== isNodeInSubgraph(tgt.id, subId);
}

function isRoutingElement(el) {
    if (!el || !el.id) return false;
    if (String(el.id).indexOf('_container') >= 0 && !el.get('subgraph')) return false;
    return true;
}

function getRouteObstacleElements() {
    if (_routeObstacleElements) return _routeObstacleElements;
    _routeObstacleElements = graph.getElements().filter(isRoutingElement);
    return _routeObstacleElements;
}

function isElementObstacleForPoint(link, point, el) {
    var src = link.get('source'), tgt = link.get('target');
    var srcId = src && src.id, tgtId = tgt && tgt.id;
    var bb = el.getBBox();
    var pad = LINK_ROUTE_PAD;
    var role = el.id === srcId ? 'source' : (el.id === tgtId ? 'target' : null);

    if (el.get('subgraph')) {
        var subId = el.get('subgraph');
        if (areBothInSubgraph(srcId, tgtId, subId)) return false;
        if (linkCrossesSubgraphBoundary(link, subId)) {
            if (isNodeInSubgraph(srcId, subId)) {
                if (isPortCorridor(point, bb, 'right')) return false;
            } else if (isNodeInSubgraph(tgtId, subId)) {
                if (isPortCorridor(point, bb, 'left')) return false;
            }
        }
        return pointInRect(point, expandRect(bb, pad));
    }

    if (el.get('isLoopShell')) {
        if (areBothInLoop(srcId, tgtId, el.id)) return false;
        if (linkCrossesLoopBoundary(link, el.id)) {
            if (isNodeInLoop(srcId, el.id)) {
                if (isPortCorridor(point, bb, 'right')) return false;
            } else if (isNodeInLoop(tgtId, el.id)) {
                if (isPortCorridor(point, bb, 'left')) return false;
            }
        }
        if (role && isInsideStrictInterior(point, bb)) return true;
        if (role && isEndpointCorridor(point, bb, role)) return false;
        return pointInRect(point, expandRect(bb, pad));
    }

    if (role) {
        if (isInsideStrictInterior(point, bb)) return true;
        if (isEndpointCorridor(point, bb, role)) return false;
        if (pointInRect(point, expandRect(bb, pad))) return true;
        return false;
    }

    var parentLoop = link.get('parentLoop');
    if (el.get('parentLoop')) {
        if (parentLoop && el.get('parentLoop') !== parentLoop) return false;
        if (!parentLoop && el.get('parentLoop')) return pointInRect(point, expandRect(bb, pad));
    }
    if (isLoopInnerNode(el.id)) {
        if (parentLoop && getLoopParentId(el.id) !== parentLoop) return false;
    }

    return pointInRect(point, expandRect(bb, pad));
}

function isLinkRouteObstacle(link, point) {
    var elements = getRouteObstacleElements();
    for (var i = 0; i < elements.length; i++) {
        if (isElementObstacleForPoint(link, point, elements[i])) return true;
    }
    return false;
}

function configureLinkRouting(link) {
    if (!link || typeof link.router !== 'function') return;
    refreshLinkEndpointGeometry(link);
    link.vertices([]);
    link.router('manhattan', {
        step: 10,
        padding: LINK_ROUTE_PAD,
        maximumLoops: 5000,
        startDirections: ['right'],
        endDirections: ['left'],
        isPointObstacle: function(point) { return isLinkRouteObstacle(link, point); }
    });
    link.connector('rounded', { radius: 8 });
    if (!link.get('parentLoop')) link.set('z', 5);
}

function rerouteAllLinks() {
    if (!graph) return;
    _routeObstacleElements = null;
    graph.getLinks().forEach(configureLinkRouting);
    _routeObstacleElements = null;
}

function linkEndpointGeometry(side) {
    return {
        anchor: {
            name: 'perpendicular',
            args: { padding: LINK_PORT_OFFSET, rotate: true }
        },
        connectionPoint: {
            name: 'boundary',
            args: {
                sticky: true,
                stroke: true,
                offset: side === 'out' ? -LINK_BOUNDARY_OFFSET : 0
            }
        }
    };
}

function resolveLinkEndpoint(cellOrId, side, preferredPortId) {
    var cellId = typeof cellOrId === 'string' ? cellOrId : (cellOrId ? cellOrId.id : '');
    var cell = typeof cellOrId === 'object' && cellOrId ? cellOrId : (graph && cellId ? graph.getCell(cellId) : null);
    var endpoint = resolvePortEndpoint(cell, side, preferredPortId);
    if (!endpoint.id && cellId) {
        endpoint.id = cellId;
        if (cellId === 'START' && side === 'out') endpoint.port = endpoint.port || 'out_trigger';
        else if (cellId === 'END' && side === 'in') endpoint.port = endpoint.port || 'in_input';
        else if (preferredPortId) endpoint.port = preferredPortId;
    }
    if (endpoint.id) {
        var geom = linkEndpointGeometry(side);
        endpoint.anchor = geom.anchor;
        endpoint.connectionPoint = geom.connectionPoint;
    }
    return endpoint;
}

function refreshLinkEndpointGeometry(link) {
    var src = link.get('source'), tgt = link.get('target');
    if (!src || !tgt || !src.id || !tgt.id) return;
    var opts = inferLinkPorts(src.id, tgt.id);
    link.source(resolveLinkEndpoint(src.id, 'out', opts.sourcePort || src.port));
    link.target(resolveLinkEndpoint(tgt.id, 'in', opts.targetPort || tgt.port));
}

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

/** Height of optional meta line(s) above I/O — must match buildNodeLayout HTML. */
function measureMetaBlockHeight(agent, displayType, type) {
    var h = 0;
    var model = (agent && agent.model) ? agent.model : '';
    var tools = (agent && agent.tools) || [];
    var agentId = (agent && agent.id) || '';
    var pinnedVersion = agentId ? getPinnedAgentVersion(agentId) : '';
    if (type === 'LLM' && model) h += WF_META_LINE_H;
    if (tools.length) h += WF_META_LINE_H;
    if (pinnedVersion) h += WF_META_LINE_H;
    if (displayType === 'branch' || type === 'PGM' || type === 'SUB' || displayType === 'loop') h += WF_META_LINE_H;
    return h;
}

/** Shared vertical layout for HTML body and JointJS port positions (must match graph.css). */
function computeWfNodeMetrics(agent, displayType, type) {
    var inputs = normalizeInputs(agent);
    var branchConds = (displayType === 'branch')
        ? ((agent && agent.conditions) || [{ label: 'True' }, { label: 'False' }])
        : [];
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : '';
    var showIdRow = agent && agent.id && agent.name && agent.id !== agent.name;

    var y = WF_HEADER_H + WF_BODY_PAD_TOP;
    var portItems = [];

    y += measureMetaBlockHeight(agent, displayType, type);
    if (showIdRow) y += WF_ID_ROW_H;

    var yInputBlock = y;
    y += WF_IO_LABEL_H;
    if (inputs.length) {
        inputs.forEach(function(inp, i) {
            portItems.push({
                id: 'in_' + inp,
                group: 'in',
                yPx: yInputBlock + WF_IO_LABEL_H + i * WF_ROW_H + WF_ROW_H / 2
            });
            y += WF_ROW_H;
        });
    } else {
        portItems.push({ id: 'in_default', group: 'in', yPx: y + WF_ROW_H / 2 });
        y += WF_ROW_H;
    }
    y += WF_IO_BLOCK_GAP;

    var yOutputBlock = y;
    y += WF_IO_LABEL_H;
    if (displayType === 'branch' && branchConds.length) {
        branchConds.forEach(function(c, i) {
            portItems.push({
                id: 'out_' + sanitizePortId(c.label),
                group: 'out',
                yPx: yOutputBlock + WF_IO_LABEL_H + i * WF_ROW_H + WF_ROW_H / 2
            });
            y += WF_ROW_H;
        });
    } else if (outName) {
        portItems.push({
            id: 'out_' + outName,
            group: 'out',
            yPx: yOutputBlock + WF_IO_LABEL_H + WF_ROW_H / 2
        });
        y += WF_ROW_H;
    } else {
        portItems.push({ id: 'out_default', group: 'out', yPx: y + WF_ROW_H / 2 });
        y += WF_ROW_H;
    }
    y += WF_BODY_PAD_BOTTOM;

    var height = y;
    return {
        height: height,
        portItems: portItems.map(function(p) {
            return {
                id: p.id,
                group: p.group,
                args: { y: portYPercent(p.yPx, height) }
            };
        })
    };
}

function unionLoopDescendantBBox(loopId) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    function addEl(nid) {
        var el = graph.getCell(nid);
        if (!el) return;
        var bb = el.getBBox();
        minX = Math.min(minX, bb.x);
        minY = Math.min(minY, bb.y);
        maxX = Math.max(maxX, bb.x + bb.width);
        maxY = Math.max(maxY, bb.y + bb.height);
        if (isLoopNode(nid) && hasLoopInners(nid)) {
            getLoopInnerIds(nid).forEach(addEl);
        }
    }
    getLoopInnerIds(loopId).forEach(addEl);
    if (!isFinite(minX)) return null;
    return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
}

function fitLoopShellToContent(loopId, opts) {
    opts = opts || {};
    var loopEl = graph.getCell(loopId);
    if (!loopEl || !loopEl.get('isLoopShell')) return;
    var u = unionLoopDescendantBBox(loopId);
    if (!u) return;
    var newW = Math.max(300, u.maxX - u.minX + LOOP_PAD * 2);
    var newH = Math.max(160, u.maxY - u.minY + LOOP_HEADER_H + LOOP_PAD + LOOP_PAD + LOOP_BOTTOM_EXTRA);
    var anchor = opts.anchor || loopEl.get('parentLoop');
    if (anchor) {
        var cur = loopEl.position();
        loopEl.resize(newW, newH);
        loopEl.position(cur.x, cur.y);
    } else {
        var old = loopEl.position();
        var nx = u.minX - LOOP_PAD;
        var ny = u.minY - LOOP_HEADER_H - LOOP_PAD;
        var dx = nx - old.x;
        var dy = ny - old.y;
        loopEl.position(nx, ny);
        loopEl.resize(newW, newH);
        if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            getLoopInnerIds(loopId).forEach(function(nid) {
                var ch = graph.getCell(nid);
                if (!ch) return;
                var p = ch.position();
                ch.position(p.x + dx, p.y + dy);
            });
        }
    }
    if (!opts.skipReposition) repositionLoopChildren(loopId);
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
    var rawType = (agent && agent.type) || 'LLM';
    var flowKind = (agent && agent.flowKind) || getNodeFlowKind(id) || '';
    if (!flowKind && (rawType === 'loop' || rawType === 'branch')) flowKind = rawType;
    var displayType = flowKind || rawType;
    var type = (flowKind === 'loop' || flowKind === 'branch') ? flowKind : rawType;
    if (displayType === 'loop' && !hasLoopInners(id)) {
        return buildCompoundLoopLayout(id, agent, getNodeStroke('loop', false), flowKind);
    }
    var stroke = getNodeStroke(displayType, isSE);
    var name = truncateText((agent && agent.name) || id, 28);
    var inputs = normalizeInputs(agent);
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : '';
    var outType = (agent && agent.outputs && agent.outputs.type) ? String(agent.outputs.type) : '';
    var model = (agent && agent.model) ? truncateText(agent.model, 32) : '';
    var tools = (agent && agent.tools) || [];
    var pinnedVersion = getPinnedAgentVersion(id) || '';

    var branchConds = (displayType === 'branch')
        ? ((agent && agent.conditions) || [{ label: 'True' }, { label: 'False' }])
        : [];
    var showIdRow = agent && agent.id && agent.name && agent.id !== agent.name;
    var metrics = computeWfNodeMetrics(agent, displayType, type);
    var height = metrics.height;
    var width = WF_NODE_WIDTH;
    var portItems = metrics.portItems;

    var iconLetter = typeIconLetters[displayType] || typeIconLetters[type] || type.charAt(0) || '?';
    var typeLabel = typeLabels[displayType] || typeLabels[type] || type;
    var html = '<div class="wf-node" xmlns="' + escHtml('http://www.w3.org/1999/xhtml') + '">';
    html += '<div class="wf-node-header" style="background:' + escHtml(stroke) + '">';
    html += '<span class="wf-node-icon">' + escHtml(iconLetter) + '</span>';
    html += '<span class="wf-node-title" title="' + escHtml((agent && agent.name) || id) + '">' + escHtml(name) + '</span>';
    html += '<span class="wf-node-type" title="' + escHtml(displayType) + '">' + escHtml(typeLabel) + '</span>';
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
    if (pinnedVersion) {
        html += '<div class="wf-node-meta wf-node-version" title="Pinned agent version">Version: ' + escHtml(pinnedVersion) + '</div>';
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
            type: type, flowKind: flowKind,
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
    var portItems = layout.portItems;
    if (!el.get('isLoopShell') && layout.config) {
        var cfg = layout.config;
        var dt = cfg.flowKind || cfg.type;
        var metrics = computeWfNodeMetrics(agentsData[cfg.id] || cfg, dt, cfg.type);
        portItems = metrics.portItems;
    }
    el.set('ports', { groups: WF_PORT_GROUPS, items: portItems });
}

function refreshNodeVisual(agentId) {
    var parentLoop = getLoopParentId(agentId);
    var el = graph.getCell(agentId);
    if (parentLoop && el && !el.get('isLoopShell')) {
        var agent = agentsData[agentId] || el.get('config');
        if (agent) {
            var layout = buildNodeLayout(agentId, agent);
            var selected = selectedCell && selectedCell.id === agentId;
            applyNodeVisual(el, layout, selected);
            el.set('config', layout.config);
        }
        layoutLoopRegion(parentLoop);
        return;
    }
    if (!el) el = graph.getCell(agentId);
    if (!el || el.get('subgraph')) return;
    if (el.get('isLoopShell')) {
        layoutLoopRegion(agentId);
        return;
    }
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
    $('#zoomIn').on('click', function() { zoomClamped(ZOOM_BTN_STEP); });
    $('#zoomOut').on('click', function() { zoomClamped(-ZOOM_BTN_STEP); });
    $('#fitToContent').on('click', fitToContent);
    $('#resetView').on('click', resetView);
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

// ─── Canvas UI ──────────────────────────────────────
function initUI() {
    var container = document.getElementById('canvasContainer');
    if (container) container.style.backgroundColor = '#ffffff';
    if (paper) {
        paper.options.background = { color: '#ffffff' };
        paper.render();
    }
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
        gridSize: 10, drawGrid: true, background: { color: '#ffffff' },
        linkPinning: false, snapLinks: { radius: 30 }, async: true,
        defaultLink: function() {
            var l = new joint.shapes.standard.Link();
            configureLinkRouting(l);
            return l;
        },
        defaultAnchor: { name: 'perpendicular', args: { padding: 0, rotate: true } },
        defaultConnectionPoint: {
            name: 'boundary',
            args: { sticky: true, stroke: true, offset: -LINK_BOUNDARY_OFFSET }
        },
        validateConnection: function(cvS, mS, cvT, mT, end, linkView) {
            if (!mT || cvS === cvT) return false;
            var sid = cvS.model.id, tid = cvT.model.id;
            var sPl = cvS.model.get('parentLoop') || (isLoopInnerNode(sid) ? getLoopParentId(sid) : null);
            var tPl = cvT.model.get('parentLoop') || (isLoopInnerNode(tid) ? getLoopParentId(tid) : null);
            var sShell = cvS.model.get('isLoopShell');
            var tShell = cvT.model.get('isLoopShell');
            if (sPl && tPl && sPl !== tPl) return false;
            if (sPl && !tPl && !tShell) return false;
            if (tPl && !sPl && !sShell) return false;
            if (graph.getLinks().some(function(l) {
                var s = l.get('source'), t = l.get('target');
                return s.id === sid && t.id === tid && s.port === mS.id && t.port === mT.id;
            })) return false;
            return true;
        },
        sorting: joint.dia.Paper.sorting.APPROX,
        viewport: function(v) { return v.model.get('type') !== 'link-tools'; },
        interactive: function(cellView) {
            if (cellView.model.get('subgraph')) {
                return { elementMove: true, labelMove: false };
            }
            if (cellView.model.get('parentLoop')) {
                return { elementMove: false, labelMove: false };
            }
            return {
                linkMove: false, elementMove: true, arrowheadMove: false,
                vertexMove: false, vertexAdd: false, vertexRemove: false
            };
        }
    });
    var loopDragState = null;
    var sgDragState = null;
    paper.on('element:pointerclick', function(ev) {
        var m = ev.model;
        if (m.get('subgraph')) return;
        var cfg = m.get('config');
        if (cfg || m.get('isLoopShell')) selectNode(m);
    });
    paper.on('link:pointerclick', function(lv) { selectLink(lv.model); });
    initCanvasPan();
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
        if (cv && cv.model.isLink()) {
            selectLink(cv.model);
            showLinkContextMenu(e.clientX, e.clientY, cv.model);
            return;
        }
        if (cv && cv.model.isElement()) {
            var subId = cv.model.get('subgraph');
            if (subId) {
                var parentEl = graph.getCell(subId);
                if (parentEl) {
                    selectNode(parentEl);
                    showNodeContextMenu(e.clientX, e.clientY, parentEl);
                    return;
                }
            }
            const cfg = cv.model.get('config');
            if (cfg && cfg.type !== 'flow') {
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
    paper.on('element:pointerdown', function(ev) {
        var m = ev.model;
        var subId = m.get('subgraph');
        if (subId) {
            sgDragState = {
                subId: subId,
                cntId: m.id,
                ox: m.position().x,
                oy: m.position().y,
                members: collectSubgraphMemberPositions(subId)
            };
            return;
        }
        if (isLoopNode(m.id) && m.get('isLoopShell')) {
            loopDragState = { loopId: m.id, ox: m.position().x, oy: m.position().y, inners: {} };
            collectLoopMemberPositions(m.id, loopDragState.inners);
        }
    });
    paper.on('element:pointermove', function(ev) {
        if (sgDragState && ev.model.id === sgDragState.cntId) {
            var dx = ev.model.position().x - sgDragState.ox;
            var dy = ev.model.position().y - sgDragState.oy;
            applySubgraphDragDelta(sgDragState, dx, dy);
            return;
        }
        if (!loopDragState || ev.model.id !== loopDragState.loopId) return;
        var m = ev.model;
        var dx = m.position().x - loopDragState.ox;
        var dy = m.position().y - loopDragState.oy;
        Object.keys(loopDragState.inners).forEach(function(nid) {
            var el = graph.getCell(nid);
            var p0 = loopDragState.inners[nid];
            if (el && p0) el.position(p0.x + dx, p0.y + dy);
        });
    });
    paper.on('element:pointerup', function() {
        loopDragState = null;
        sgDragState = null;
        updateSubgraphContainerPositions();
        rerouteAllLinks();
    });
    graph.on('add', function(cell) {
        if (!cell.isLink || !cell.isLink()) return;
        if (cell.get('parentLoop')) return;
        var pl = getLinkParentLoop(cell);
        if (!pl) return;
        cell.set('parentLoop', pl);
        if (!subgraphRanges[pl]) subgraphRanges[pl] = { nodes: [], subgraphs: [], edges: [] };
        var s = cell.get('source'), t = cell.get('target');
        if (s && s.id && t && t.id) {
            var edges = subgraphRanges[pl].edges || [];
            var dup = edges.some(function(e) { return e[0] === s.id && e[1] === t.id; });
            if (!dup) edges.push([s.id, t.id]);
            subgraphRanges[pl].edges = edges;
        }
        layoutLoopRegion(pl);
        saveToHistory();
    });
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

/** Pan canvas with grab hand (blank drag, middle mouse, or Space+drag). */
function initCanvasPan() {
    var $panel = $('#paper_panel');
    var $container = $('#canvasContainer');
    var pan = null;
    var blankMoved = false;
    var spacePan = false;

    function setCursor(c) {
        if ($panel.length) $panel.css('cursor', c);
        if ($container.length) $container.css('cursor', c);
    }

    function isFormTarget(el) {
        return $(el).is('input, textarea, select') || el.isContentEditable;
    }

    function startPan(clientX, clientY) {
        if (!paper) return;
        var tr = paper.translate();
        pan = { x: clientX, y: clientY, tx: tr.tx, ty: tr.ty };
        setCursor('grabbing');
    }

    function endPan() {
        pan = null;
        setCursor(spacePan ? 'grab' : 'grab');
    }

    setCursor('grab');

    $(document).on('keydown.canvaspan', function(e) {
        if (e.code !== 'Space' || e.repeat || isFormTarget(e.target)) return;
        e.preventDefault();
        spacePan = true;
        setCursor('grab');
    });
    $(document).on('keyup.canvaspan', function(e) {
        if (e.code !== 'Space') return;
        spacePan = false;
        endPan();
    });

    $(document).on('mousemove.canvaspan', function(e) {
        if (!pan || !paper) return;
        if (Math.abs(e.clientX - pan.x) > 2 || Math.abs(e.clientY - pan.y) > 2) blankMoved = true;
        paper.translate(pan.tx + e.clientX - pan.x, pan.ty + e.clientY - pan.y);
    });
    $(document).on('mouseup.canvaspan', function() {
        if (pan) endPan();
    });

    if (!paper) return;

    paper.on('blank:pointerdown', function(evt) {
        if (evt.button === 0 || spacePan) {
            blankMoved = false;
            startPan(evt.clientX, evt.clientY);
        }
    });
    paper.on('blank:pointerup', function() {
        if (!blankMoved) deselectAll();
        endPan();
    });

    var el = paper.el;
    if (el) {
        el.addEventListener('mousedown', function(e) {
            if (e.button === 1) {
                blankMoved = false;
                startPan(e.clientX, e.clientY);
                e.preventDefault();
            }
        });
    }
}

// ─── Load components ────────────────────────────────
async function loadComponents() {
    try {
        const [ar, gr, tr, lr] = await Promise.all([
            fetch('/agents/api/list'), fetch('/graph/api/list'), fetch('/tools/api/list'),
            fetch('/llms/api/list')
        ]);
        if (ar.ok) {
            const data = await ar.json();
            allAgents = data;
            data.forEach(function(a) { if (!agentsData[a.id]) agentsData[a.id] = a; });
        }
        if (gr.ok) {
            allGraphs = await gr.json();
            if (typeof graphsById !== 'object' || graphsById === null) graphsById = {};
            (allGraphs || []).forEach(function(g) {
                if (!g || !g.id) return;
                var prev = graphsById[g.id];
                if (!prev) {
                    graphsById[g.id] = g;
                    return;
                }
                graphsById[g.id] = Object.assign({}, prev, g, {
                    nodes: prev.nodes || g.nodes,
                    edges: prev.edges || g.edges,
                    flowNodes: prev.flowNodes || g.flowNodes,
                    bindings: prev.bindings || g.bindings
                });
            });
        }
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
        var parentLoop = findLoopAtPoint(pos);
        if (parentLoop && (d.type === 'agent' || d.type === 'tool')) {
            id = d.id || (d.type + '_' + (++nodeCounter));
            if (d.type === 'agent') {
                if (!agentsData[id]) {
                    agentsData[id] = d.data ? JSON.parse(JSON.stringify(d.data)) :
                        { id: id, name: id, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
                }
                enrichAgentMeta(id);
            } else {
                agentsData[id] = { id: id, name: d.data ? d.data.name || id : 'Tool', type: 'tool',
                    inputs: (d.data && d.data.inputs) || [], outputs: { name: 'output', type: 'str' } };
            }
            _addNodeInsideLoop(parentLoop, id, pos);
            return;
        }
        if (parentLoop && d.type === 'subgraph') {
            var innerData = (d.data && d.data.nodes) ? d.data : null;
            if (!innerData && d.data && d.data.id && graphsById && graphsById[d.data.id]) {
                innerData = graphsById[d.data.id];
            }
            if (innerData) { _embedSubgraphInLoop(parentLoop, innerData, pos); return; }
        }
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
        } else if (d.type === 'loop') {
            id = 'loop_' + (++nodeCounter);
            _addLoopAt(id, pos, null);
        } else if (d.type === 'subgraph') {
            id = d.id || ('subgraph_' + (++nodeCounter));
            var srcData = (d.data && d.data.nodes) ? d.data : null;
            if (!srcData && d.data && d.data.id && graphsById && graphsById[d.data.id]) srcData = graphsById[d.data.id];
            var sgName = (d.data && d.data.name) || d.id || 'Subgraph';
            agentsData[id] = { id: id, name: sgName, type: 'SUB', inputs: ['input'], outputs: { name: 'output', type: 'list' } };
            _expandSubgraphAt(id, srcData, pos);
        } else if (d.type === 'branch') {
            id = 'branch_' + (++nodeCounter);
            cfg = { id: id, name: 'Branch', type: 'branch', inputs: ['input'], outputs: { name: 'output', type: 'dict' }, conditions: [{ label: 'True', field: '', op: 'not_empty', value: '' }, { label: 'False', field: '', op: 'empty', value: '' }] };
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

function _ensureLoopFlowNode(loopId, name, subgraphId) {
    if (!currentGraph) currentGraph = {};
    if (!currentGraph.flowNodes) currentGraph.flowNodes = {};
    if (!currentGraph.flowNodes[loopId]) {
        currentGraph.flowNodes[loopId] = {
            kind: 'loop',
            name: name || 'Loop',
            subgraphId: subgraphId || null,
            loopConfig: { loopType: 'foreach', array: '{{ text }}' }
        };
    }
    _applyFlowNodeMeta(loopId, currentGraph.flowNodes[loopId]);
}

/** Flow-control Loop: single compound node; inner agents rendered inside its body. */
function _addLoopAt(loopId, pos, srcData) {
    agentsData[loopId] = {
        id: loopId,
        name: (srcData && srcData.name) || 'Loop',
        type: 'loop',
        flowKind: 'loop',
        inputs: ['input'],
        outputs: { name: 'output', type: 'list' },
        loopConfig: { loopType: 'foreach', array: '{{ text }}' }
    };
    _ensureLoopFlowNode(loopId, agentsData[loopId].name, srcData && srcData.id);
    if (!subgraphRanges[loopId]) subgraphRanges[loopId] = { nodes: [], subgraphs: [] };
    if (srcData && srcData.nodes && srcData.nodes.length) {
        _embedSubgraphInLoop(loopId, srcData, pos);
        return;
    }
    var loopEl = createNode(loopId);
    loopEl.position(pos.x, pos.y);
    graph.addCell(loopEl);
    persistFlowNode(loopId);
    saveToHistory();
}

function _refreshLoopVisual(loopId) {
    if (hasLoopInners(loopId)) {
        layoutLoopRegion(loopId);
        return;
    }
    var el = graph.getCell(loopId);
    if (!el) return;
    if (el.get('isLoopShell')) {
        var pos = el.position();
        el.remove();
        el = createNode(loopId);
        el.position(pos.x, pos.y);
        graph.addCell(el);
    }
    var layout = buildNodeLayout(loopId, agentsData[loopId] || el.get('config'));
    applyNodeVisual(el, layout, selectedCell && selectedCell.id === loopId);
    el.set('config', layout.config);
}

function _addNodeInsideLoop(loopId, nodeId, pos) {
    if (!subgraphRanges[loopId]) subgraphRanges[loopId] = { nodes: [], subgraphs: [], edges: [] };
    enrichAgentMeta(nodeId);
    if (subgraphRanges[loopId].nodes.indexOf(nodeId) < 0) subgraphRanges[loopId].nodes.push(nodeId);
    var stray = graph.getCell(nodeId);
    if (stray && stray.get('parentLoop') !== loopId && !isLoopNode(nodeId)) {
        stray.remove();
    }
    layoutLoopRegion(loopId);
    saveToHistory();
}

function _embedSubgraphInLoop(loopId, srcData, pos) {
    if (!srcData || !srcData.nodes) return;
    if (!subgraphRanges[loopId]) subgraphRanges[loopId] = { nodes: [], subgraphs: [] };
    (srcData.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        enrichAgentMeta(nid);
        if (!agentsData[nid]) {
            agentsData[nid] = { id: nid, name: nid, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
        }
        if (subgraphRanges[loopId].nodes.indexOf(nid) < 0) subgraphRanges[loopId].nodes.push(nid);
        var stray = graph.getCell(nid);
        if (stray && stray.get('parentLoop') !== loopId && !isLoopNode(nid)) stray.remove();
    });
    subgraphRanges[loopId].edges = filterInnerEdges(srcData.edges);
    if (!subgraphRanges[loopId].subgraphs) subgraphRanges[loopId].subgraphs = [];
    (srcData.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        var a = agentsData[nid];
        if (a && a.type === 'SUB') subgraphRanges[loopId].subgraphs.push(nid);
    });
    if (srcData.id && currentGraph && currentGraph.flowNodes && currentGraph.flowNodes[loopId]) {
        currentGraph.flowNodes[loopId].subgraphId = srcData.id;
        agentsData[loopId].subgraphId = srcData.id;
    }
    var loopEl = graph.getCell(loopId);
    if (!loopEl) {
        loopEl = createNode(loopId);
        loopEl.position(pos.x, pos.y);
        graph.addCell(loopEl);
    }
    layoutLoopRegion(loopId);
    persistFlowNode(loopId);
    saveToHistory();
}

// ─── Expand subgraph at drop position (subgraph list only — purple SUB) ──
function _expandSubgraphAt(sgId, srcData, pos) {
    if (!srcData || !srcData.nodes || !srcData.nodes.length) {
        subgraphRanges[sgId] = { nodes: [], subgraphs: [], edges: [] };
        _drawSubgraphContainer(sgId);
        saveToHistory();
        return;
    }
    (srcData.nodes || []).forEach(function(nid) {
        if (nid === 'START' || nid === 'END') return;
        enrichAgentMeta(nid);
        if (!agentsData[nid]) agentsData[nid] = { id: nid, name: nid, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
    });
    var innerNodes = (srcData.nodes || []).filter(function(n) { return n !== 'START' && n !== 'END'; });
    var innerEdges = filterInnerEdges(srcData.edges);
    subgraphRanges[sgId] = { nodes: innerNodes, subgraphs: [], edges: innerEdges };
    var ordered = orderNodesHorizontal(innerNodes, innerEdges);
    var x0 = pos.x + 50, y0 = pos.y + 60;
    var x = x0, gap = 56;
    ordered.forEach(function(nid) {
        var el = createNode(nid);
        el.position(x, y0);
        graph.addCell(el);
        x += el.size().width + gap;
    });
    addInnerGraphLinks(innerNodes, innerEdges);
    reattachLinkPorts();
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
    if (!isSE && isLoopNode(id)) {
        agent.type = 'loop';
        agent.flowKind = 'loop';
        if (!agent.loopConfig) agent.loopConfig = { loopType: 'foreach', array: '{{ text }}' };
        if (hasLoopInners(id)) return createLoopShell(id, agent, estimateLoopRegionSize(id));
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
    link.source(resolveLinkEndpoint(sourceId, 'out', opts.sourcePort));
    link.target(resolveLinkEndpoint(targetId, 'in', opts.targetPort));
    var srcCell = graph.getCell(sourceId);
    var color = '#666', sn = srcCell;
    if (sn) {
        var sc = sn.get('config') || {};
        var st = sc.flowKind || sc.type || 'PGM';
        color = (nodeStyles[st] || nodeStyles.PGM).stroke;
    }
    link.attr({
        line: {
            stroke: color, strokeWidth: 2,
            targetMarker: { type: 'path', d: 'M 10 -5 0 0 10 5 z', fill: color }
        },
        wrapper: { strokeWidth: 8, stroke: 'transparent', fill: 'none' }
    });
    configureLinkRouting(link);
    return link;
}

function reattachLinkPorts() {
    graph.getLinks().forEach(function(link) {
        configureLinkRouting(link);
    });
}

function inferBranchSourcePort(sourceId, targetId) {
    var srcCfg = agentsData[sourceId] || {};
    if (srcCfg.flowKind !== 'branch' && srcCfg.type !== 'branch') return null;
    var conds = srcCfg.conditions || [];
    if (!conds.length) return null;
    var wf = currentGraph || {};
    var outs = [];
    (wf.edges || []).forEach(function(e) {
        var s = Array.isArray(e[0]) ? e[0][0] : e[0];
        var t = Array.isArray(e[1]) ? e[1][0] : e[1];
        if (s === sourceId) outs.push(t);
    });
    var idx = outs.indexOf(targetId);
    if (idx < 0) idx = 0;
    var c = conds[idx] || conds[0];
    return 'out_' + sanitizePortId(c.label);
}

function inferLinkPorts(sourceId, targetId, linkHint) {
    var opts = {};
    var srcCfg = (agentsData[sourceId]) || (graph.getCell(sourceId) && graph.getCell(sourceId).get('config'));
    var tgtCfg = (agentsData[targetId]) || (graph.getCell(targetId) && graph.getCell(targetId).get('config'));
    var srcCell = graph.getCell(sourceId);
    var tgtCell = graph.getCell(targetId);

    if (srcCfg) {
        if ((srcCfg.flowKind === 'branch' || srcCfg.type === 'branch') && srcCfg.conditions && srcCfg.conditions.length) {
            var branchPort = inferBranchSourcePort(sourceId, targetId);
            if (linkHint && linkHint.branchLabel) {
                branchPort = 'out_' + sanitizePortId(linkHint.branchLabel);
            } else if (linkHint && linkHint.sourcePort) {
                branchPort = linkHint.sourcePort;
            }
            if (!branchPort || !srcCell || !(srcCell.getPorts() || []).some(function(p) { return p.id === branchPort; })) {
                branchPort = 'out_' + sanitizePortId(srcCfg.conditions[0].label);
            }
            opts.sourcePort = branchPort;
        } else if (srcCfg.outputs && srcCfg.outputs.name) {
            opts.sourcePort = 'out_' + srcCfg.outputs.name;
        }
    }
    if (tgtCfg && tgtCfg.inputs && tgtCfg.inputs.length) {
        var inputs = normalizeInputs(tgtCfg);
        var outName = srcCfg && srcCfg.outputs ? srcCfg.outputs.name : null;
        var picked = null;
        if (linkHint && linkHint.targetPort) {
            picked = linkHint.targetPort;
        } else if (outName && inputs.indexOf(outName) >= 0) {
            picked = 'in_' + outName;
        } else if (srcCfg && srcCfg.flowKind === 'loop' && inputs.indexOf('text') >= 0) {
            picked = 'in_text';
        } else if (inputs.length) {
            picked = 'in_' + inputs[0];
        }
        if (picked && tgtCell && tgtCell.getPorts) {
            var inPorts = (tgtCell.getPorts() || []).filter(function(p) { return p.group === 'in'; });
            if (!inPorts.some(function(p) { return p.id === picked; }) && inPorts.length) {
                picked = inPorts[0].id;
            }
        }
        opts.targetPort = picked;
    }
    if (srcCell && srcCell.getPorts && opts.sourcePort) {
        var outPorts = (srcCell.getPorts() || []).filter(function(p) { return p.group === 'out'; });
        if (!outPorts.some(function(p) { return p.id === opts.sourcePort; }) && outPorts.length) {
            opts.sourcePort = outPorts[0].id;
        }
    }
    return opts;
}

// ─── Render workflow ────────────────────────────────
function collectSubgraphInnerNodes() {
    var inner = [];
    Object.keys(subgraphRanges).forEach(function(sgId) {
        if (isLoopNode(sgId)) return;
        (subgraphRanges[sgId].nodes || []).forEach(function(n) {
            if (inner.indexOf(n) < 0) inner.push(n);
        });
    });
    return inner;
}

function renderWorkflow(wf) {
    if (!wf || !wf.nodes || !wf.edges) { createDefaultWorkflow(); return; }
    graph.clear();
    subgraphRanges = {};
    mergeFlowNodesFromGraph(wf);
    syncFlowNodeAgents(wf);
    var expanded = expandSubgraph(wf);
    var nestedLoopOrder = discoverNestedLoops(wf);
    nestedLoopOrder.forEach(function(nid) { expandLoopInner(nid, wf); });
    var innerFromSubs = collectSubgraphInnerNodes();
    var topNodes = expanded.nodes.filter(function(n) {
        return n !== 'START' && n !== 'END' && !isLoopInnerNode(n);
    });
    innerFromSubs.forEach(function(n) {
        if (topNodes.indexOf(n) < 0 && !isLoopInnerNode(n)) topNodes.push(n);
    });
    var allNodes = ['START'].concat(topNodes, ['END']);
    var nodeCells = allNodes.map(function(id) { return createNode(id); });
    var linkCells = [];
    expanded.edges.forEach(function(e) {
        if (graph.getCell(e[0]) || allNodes.indexOf(e[0]) >= 0)
            if (graph.getCell(e[1]) || allNodes.indexOf(e[1]) >= 0)
                linkCells.push(createLink(e[0], e[1]));
    });
    graph.resetCells(nodeCells.concat(linkCells));
    var savedLayout = wf.visualData && wf.visualData.layout;
    var hasSavedLayout = savedLayout && Object.keys(savedLayout).length > 0;
    if (!hasSavedLayout) {
        var layoutRankSep = nestedLoopOrder.length ? 240 : 160;
        joint.layout.DirectedGraph.layout(graph, {
            rankDir: 'LR', nodeSep: 100, rankSep: layoutRankSep, edgeSep: 50, marginX: 48, marginY: 48
        });
        reattachLinkPorts();
        drawSubgraphContainers();
        getRootLoopIds(wf).forEach(function(lid) { layoutLoopRegion(lid); });
        finalizeLoopLayout(wf);
        syncNestedLoopShellPositions();
        resolveLoopTopLevelOverlaps();
        finalizeLoopLayout(wf);
        syncNestedLoopShellPositions();
        reattachLinkPorts();
        updateSubgraphContainerPositions();
    } else {
        // Saved layout: still materialize loop inner nodes, then restore coordinates.
        getRootLoopIds(wf).forEach(function(lid) { layoutLoopRegion(lid); });
        drawSubgraphContainers();
        applyCanvasLayoutPositions(savedLayout);
        getRootLoopIds(wf).forEach(function(lid) {
            fitLoopShellToContent(lid, { anchor: true, skipReposition: true });
        });
        syncNestedLoopShellPositions();
        reattachLinkPorts();
        updateSubgraphContainerPositions();
    }
    fitToContent(); saveToHistory();
    syncCurrentGraphFromCanvas();
}

// ─── Subgraph expand ────────────────────────────────
function expandSubgraph(wf) {
    var nodes = [], edges = [];
    subgraphRanges = {};
    var isSub = function(nid) {
        if (getNodeFlowKind(nid, wf) === 'loop') return false;
        if (agentsData[nid] && agentsData[nid].type === 'SUB') return true;
        if (graphsById && graphsById[nid]) return true;
        if (wf.visualData && wf.visualData.nodes) {
            var vn = wf.visualData.nodes.find(function(n) { return n.id === nid || n.originalId === nid; });
            if (vn && (vn.type === 'subgraph' ||
                (vn.data && vn.data.type === 'SUB'))) return true;
        }
        return false;
    };
    var ensureRange = function(nid) { if (!subgraphRanges[nid]) subgraphRanges[nid] = { nodes: [], subgraphs: [] }; };
    var getEntries = function(subId) {
        var sub = resolveSubgraphGraph(subId, wf);
        if (!sub || !sub.edges) return [];
        return sub.edges.filter(function(e) { return e[0] === 'START'; }).map(function(e) { return e[1]; }).reduce(function(a, t) { return a.concat(isSub(t) ? getEntries(t) : [t]); }, []);
    };
    var getExits = function(subId) {
        var sub = resolveSubgraphGraph(subId, wf);
        if (!sub || !sub.edges) return [];
        return sub.edges.filter(function(e) { return e[1] === 'END'; }).map(function(e) { return e[0]; }).reduce(function(a, s) { return a.concat(isSub(s) ? getExits(s) : [s]); }, []);
    };
    var expandRecursive = function(subId) {
        var sub = resolveSubgraphGraph(subId, wf);
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

function expandLoopInner(loopNid, wf) {
    wf = wf || currentGraph || {};
    var fn = getLoopFlowMeta(loopNid, wf);
    if (!fn || fn.kind !== 'loop') return;
    var sub = fn.subgraphId ? resolveSubgraphGraph(fn.subgraphId, wf) : resolveSubgraphGraph(loopNid, wf);
    if (!subgraphRanges[loopNid]) subgraphRanges[loopNid] = { nodes: [], subgraphs: [], edges: [] };
    if (!sub || !sub.nodes) return;

    var subFn = sub.flowNodes || {};
    Object.keys(subFn).forEach(function(nid) { _applyFlowNodeMeta(nid, subFn[nid]); });

    (sub.nodes || []).forEach(function(n) {
        if (n === 'START' || n === 'END') return;
        var childFn = subFn[n];
        if (childFn && childFn.kind === 'loop') {
            expandLoopInner(n, wf);
            if (subgraphRanges[loopNid].nodes.indexOf(n) < 0) subgraphRanges[loopNid].nodes.push(n);
            return;
        }
        enrichAgentMeta(n);
        if (!agentsData[n]) {
            agentsData[n] = { id: n, name: n, type: 'LLM', inputs: [], outputs: { name: 'output', type: 'str' } };
        }
        if (subgraphRanges[loopNid].nodes.indexOf(n) < 0) subgraphRanges[loopNid].nodes.push(n);
    });

    agentsData[loopNid] = agentsData[loopNid] || { id: loopNid };
    agentsData[loopNid].type = 'loop';
    agentsData[loopNid].flowKind = 'loop';
    agentsData[loopNid].name = fn.name || agentsData[loopNid].name || loopNid;
    agentsData[loopNid].loopConfig = fn.loopConfig || agentsData[loopNid].loopConfig || {};
    if (fn.subgraphId) agentsData[loopNid].subgraphId = fn.subgraphId;

    var children = subgraphRanges[loopNid].nodes;
    subgraphRanges[loopNid].edges = filterInnerEdges(sub.edges).filter(function(e) {
        return children.indexOf(e[0]) >= 0 && children.indexOf(e[1]) >= 0;
    });
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
        // Include loop inner children in the bounding box
        if (isLoopNode(nid) && hasLoopInners(nid)) {
            var shell = graph.getCell(nid);
            if (shell) bbox = bbox ? bbox.union(shell.getBBox()) : shell.getBBox();
            getLoopInnerIds(nid).forEach(function(innerId) {
                var inner = graph.getCell(innerId);
                if (inner) bbox = bbox ? bbox.union(inner.getBBox()) : inner.getBBox();
            });
        }
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
    if (isLoopNode(subId)) return;
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
    var stroke = nodeStyles.SUB.stroke;
    var fill = 'rgba(118,75,162,0.08)';
    var labelName = (getGraphFlowNodes()[subId] && getGraphFlowNodes()[subId].name) ||
        (agentsData[subId] ? agentsData[subId].name : null) ||
        (graphsById[subId] ? (graphsById[subId].name || subId) : subId);
    var labelText = 'SUB · ' + labelName;
    var rect = new joint.shapes.standard.Rectangle({
        id: cntId, z: -10,
        position: { x: bbox.x - pad, y: bbox.y - pad },
        size: { width: bbox.width + pad * 2, height: bbox.height + pad * 2 },
        attrs: {
            body: {
                fill: fill, stroke: stroke, strokeDasharray: '8 4', rx: 14, ry: 14, strokeWidth: 1.5,
                cursor: 'move'
            },
            label: {
                text: labelText,
                fill: stroke, fontSize: 13, fontWeight: 'bold', refX: 14, refY: 14,
                textAnchor: 'start', textVerticalAnchor: 'top', pointerEvents: 'none'
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
    if (node.get('isLoopShell')) {
        node.attr('body/stroke', '#ff5722');
        node.attr('body/strokeWidth', 3);
    } else if (cfg && cfg.id && cfg.type !== 'flow') {
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
            if (selectedCell.get('isLoopShell')) {
                selectedCell.attr('body/stroke', nodeStyles.loop.stroke);
                selectedCell.attr('body/strokeWidth', 1.5);
            } else if (cfg && cfg.type === 'flow') {
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

function buildAgentVersionSelectorHtml(agentId) {
    var pinned = getPinnedAgentVersion(agentId) || '';
    var html = '<div class="mb-2"><label class="fw-bold small">Agent version pin</label>';
    html += '<select id="propAgentVersionSelect" class="form-select form-select-sm">';
    html += '<option value="">(use current version)</option>';
    html += '</select>';
    html += '<div id="propAgentVersionHint" class="small text-muted mt-1">';
    html += pinned ? ('Pinned: ' + escHtml(pinned)) : 'Using current agent version';
    html += '</div></div>';
    return html;
}

function loadAgentVersions(agentId) {
    if (agentVersionCache[agentId]) {
        return Promise.resolve(agentVersionCache[agentId]);
    }
    return fetch('/agents/api/' + encodeURIComponent(agentId) + '/versions')
        .then(function(r) { return r.ok ? r.json() : { versions: [] }; })
        .then(function(data) {
            var versions = (data && data.versions) || [];
            agentVersionCache[agentId] = versions;
            return versions;
        })
        .catch(function() { return []; });
}

function renderAgentVersionSelector(agentId) {
    var $sel = $('#propAgentVersionSelect');
    var $hint = $('#propAgentVersionHint');
    if (!$sel.length) return;
    var pinned = getPinnedAgentVersion(agentId) || '';
    $sel.prop('disabled', true);
    $sel.html('<option value="">Loading...</option>');
    loadAgentVersions(agentId).then(function(versions) {
        var opts = ['<option value="">(use current version)</option>'];
        versions.forEach(function(v) {
            var note = (v.change_note || '').trim();
            var lbl = v.version + (note ? (' | ' + note) : '');
            opts.push('<option value="' + escHtml(v.version) + '"' + (pinned === v.version ? ' selected' : '') + '>' + escHtml(lbl) + '</option>');
        });
        $sel.html(opts.join(''));
        $sel.prop('disabled', false);
        if (pinned) $sel.val(pinned);
        $hint.text(pinned ? ('Pinned: ' + pinned) : 'Using current agent version');
    });
}

function bindAgentVersionSelectorEvents(agentId) {
    $('#propAgentVersionSelect').off('change').on('change', function() {
        var v = $(this).val() || '';
        setPinnedAgentVersion(agentId, v);
        $('#propAgentVersionHint').text(v ? ('Pinned: ' + v) : 'Using current agent version');
        refreshNodeVisual(agentId);
    });
}

// ─── Property panel ─────────────────────────────────
function showPropertyPanel(node) {
    $('#propertyPanel').removeClass('d-none');
    var cfg = node.get('config') || {}, prompt = node.get('prompt') || {};
    var type = cfg.flowKind || cfg.type || 'Unknown';
    var id = cfg.id || node.id, name = cfg.name || id;
    $('#propName').val(name);
    var showIO = ['LLM','PGM','branch','loop','tool','SUB'].indexOf(type) >= 0 || (cfg.inputs && cfg.inputs.length > 0);
    $('#ioMappingSection').toggle(showIO);
    var icon = typeIcons[type] || 'fa-cube';
    var html = '<div class="card mb-3"><div class="card-header bg-primary text-white"><h6 class="mb-0"><i class="fas ' + icon + ' me-2"></i>' + name + '</h6></div><div class="card-body">';
    html += '<div class="mb-2"><label class="fw-bold small">ID</label><input class="form-control form-control-sm" value="' + id + '" readonly></div>';
    html += '<div class="mb-2"><label class="fw-bold small">Type</label><span class="badge ms-2 ' + (type==='LLM'?'bg-indigo':type==='PGM'?'bg-success':type==='SUB'?'bg-purple':type==='branch'?'bg-warning':type==='loop'?'bg-info':'bg-secondary') + '">' + type + '</span></div>';
    if (type === 'LLM') html += buildLlmSelectorHtml(cfg.model || '');
    if (id !== 'START' && id !== 'END' && !cfg.flowKind && type !== 'flow' && type !== 'branch' && type !== 'loop') {
        html += buildAgentVersionSelectorHtml(id);
    }
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
    if (id !== 'START' && id !== 'END' && !cfg.flowKind && type !== 'flow' && type !== 'branch' && type !== 'loop') {
        renderAgentVersionSelector(id);
        bindAgentVersionSelectorEvents(id);
    }
    var isBranchFlow = (cfg.flowKind === 'branch' || type === 'branch');
    $('#branchConfigSection').toggleClass('d-none', !isBranchFlow);
    var isLoopFlow = (cfg.flowKind === 'loop' || type === 'loop');
    $('#loopConfigSection').toggleClass('d-none', !isLoopFlow);
    if (isLoopFlow) {
        var lc = cfg.loopConfig || {};
        $('#loopType').val(lc.loopType || 'foreach');
        $('#loopArray').val(lc.array || '');
        $('#loopCount').val(lc.count || 10);
        updateLoopConfigVisibility(lc.loopType || 'foreach');
        renderLoopItemBindings(id);
        $('#loopType').off('change.loopPanel').on('change.loopPanel', function() {
            updateLoopConfigVisibility($(this).val());
            syncLoopPanelToAgent(id);
        });
        $('#loopArray, #loopCount').off('change.loopPanel input.loopPanel')
            .on('change.loopPanel input.loopPanel', function() { syncLoopPanelToAgent(id); });
        $('#syncLoopItemBindings').off('click').on('click', function() {
            var meta = getLoopFlowMeta(id);
            var subId = (meta && meta.subgraphId) || agentsData[id].subgraphId;
            var fields = collectSubgraphInputFields(subId);
            if (!agentsData[id].loopConfig) agentsData[id].loopConfig = {};
            var ib = agentsData[id].loopConfig.itemBindings = agentsData[id].loopConfig.itemBindings || {};
            fields.forEach(function(field) {
                if (!ib[field]) ib[field] = '{{ ' + field + ' }}';
            });
            persistFlowNode(id);
            renderLoopItemBindings(id);
        });
    }
    if (isBranchFlow) renderBranchConditionsPanel(id, cfg.conditions || []);
    renderIOMapping(node);
}

function renderBranchConditionsPanel(nodeId, conditions) {
    var $box = $('#branchConditions').empty();
    if (!conditions.length) {
        conditions = [{ label: 'True', field: '', op: 'not_empty', value: '' }];
    }
    conditions.forEach(function(raw, i) {
        var c = normalizeBranchCondition(raw);
        var opOpts = BRANCH_OPS.map(function(o) {
            return '<option value="' + o.id + '"' + (o.id === c.op ? ' selected' : '') + '>' + o.label + '</option>';
        }).join('');
        var needsVal = (BRANCH_OPS.find(function(o) { return o.id === c.op; }) || {}).needsValue;
        var row = $('<div class="branch-cond-row border rounded p-2 mb-2" data-idx="' + i + '">');
        row.append(
            '<div class="row g-1 align-items-center">' +
            '<div class="col-12"><label class="small text-muted">Label</label>' +
            '<input type="text" class="form-control form-control-sm cond-label" value="' + escHtml(c.label) + '"></div>' +
            '<div class="col-5"><label class="small text-muted">Field</label></div>' +
            '<div class="col-7"><label class="small text-muted">Operator</label></div>' +
            '<div class="col-5 cond-field-wrap"></div>' +
            '<div class="col-7"><select class="form-select form-select-sm cond-op">' + opOpts + '</select></div>' +
            '<div class="col-12 cond-value-wrap mt-1' + (needsVal ? '' : ' d-none') + '">' +
            '<label class="small text-muted">Compare value</label>' +
            '<input type="text" class="form-control form-control-sm cond-value" value="' + escHtml(c.value) + '"></div>' +
            '<div class="col-12 text-end"><button type="button" class="btn btn-sm btn-outline-danger btn-remove-cond"><i class="fas fa-trash"></i></button></div>' +
            '</div>'
        );
        row.find('.cond-field-wrap').html(buildFieldSelectHtml(nodeId, c.field, 'cond-field'));
        $box.append(row);
    });
    $('#addBranchCondition').off('click').on('click', function() {
        var cur = readBranchConditionsFromPanel();
        cur.push({ label: 'Else', field: '', op: 'empty', value: '' });
        renderBranchConditionsPanel(nodeId, cur);
    });
    $box.off('change', '.cond-op').on('change', '.cond-op', function() {
        var op = $(this).val();
        var needs = (BRANCH_OPS.find(function(o) { return o.id === op; }) || {}).needsValue;
        $(this).closest('.branch-cond-row').find('.cond-value-wrap').toggleClass('d-none', !needs);
    });
    $box.off('click', '.btn-remove-cond').on('click', '.btn-remove-cond', function() {
        $(this).closest('.branch-cond-row').remove();
        if (!$box.find('.branch-cond-row').length) {
            renderBranchConditionsPanel(nodeId, [{ label: 'True', field: '', op: 'not_empty', value: '' }]);
        }
    });
}

function readBranchConditionsFromPanel() {
    var list = [];
    $('#branchConditions .branch-cond-row').each(function() {
        list.push({
            label: $(this).find('.cond-label').val() || 'Branch',
            field: $(this).find('.cond-field').val() || '',
            op: $(this).find('.cond-op').val() || 'not_empty',
            value: $(this).find('.cond-value').val() || ''
        });
    });
    return list;
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
            '<div class="d-flex align-items-center mb-2 mapping-row" data-input="' + escHtml(inp) + '">' +
            '<span class="badge bg-secondary me-2" style="min-width:60px">' + escHtml(inp) + '</span>' +
            buildMappingSelectHtml(nid, val) +
            '</div>'
        );
    });
    if (!inputs.length) $ic.html('<p class="text-muted small mb-0">No inputs</p>');
    $oc.append('<div class="d-flex align-items-center mb-1"><span class="badge bg-success me-2" style="min-width:60px">' + escHtml(outName) + '</span><code class="small text-muted">{{ ' + escHtml(nid) + '.' + escHtml(outName) + ' }}</code></div>');
    $('.mapping-select').off('change').on('change', function() {
        var row = $(this).closest('.mapping-row');
        var field = row.data('input');
        if (!graphBindings[nid]) graphBindings[nid] = {};
        graphBindings[nid][field] = $(this).val();
    });
}
function hidePropertyPanel() {
    document.getElementById('propertyPanel').classList.add('d-none');
    $('#branchConfigSection').addClass('d-none');
    $('#loopConfigSection').addClass('d-none');
}

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
    if ($('#branchConditions .branch-cond-row').length) {
        cfg.conditions = readBranchConditionsFromPanel();
    }
    cfg.prompt_template = prompt;
    node.set('config', cfg);
    node.set('prompt', prompt);
    if (agentsData[agentId]) {
        Object.assign(agentsData[agentId], cfg);
        agentsData[agentId].prompt_template = prompt;
        agentsData[agentId].conditions = cfg.conditions;
    }
    persistFlowNode(agentId);
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
function saveToHistory() {
    historyStack.push(JSON.stringify(graph.toJSON()));
    redoStack = [];
    if ($('#btnUndo').length) $('#btnUndo').prop('disabled', false);
}
function undo() { if (historyStack.length <= 1) return; redoStack.push(historyStack.pop()); graph.fromJSON(JSON.parse(historyStack[historyStack.length-1])); deselectAll(); }
function redo() { if (!redoStack.length) return; historyStack.push(redoStack.pop()); graph.fromJSON(JSON.parse(historyStack[historyStack.length-1])); deselectAll(); }

function deleteCell(cell) {
    if (!cell) return false;
    if (cell.isLink()) {
        cell.remove();
        return true;
    }
    if (!cell.isElement()) return false;
    var id = cell.id;
    if (id === 'START' || id === 'END') return false;
    if (cell.get('subgraph')) {
        var subId = cell.get('subgraph');
        var parent = graph.getCell(subId);
        if (parent) return deleteCell(parent);
        cell.remove();
        return true;
    }
    var cnt = graph.getCell(id + '_container');
    if (cnt) cnt.remove();
    if (subgraphRanges[id]) {
        if (isLoopNode(id)) {
            (subgraphRanges[id].nodes || []).forEach(function(nid) {
                var inner = graph.getCell(nid);
                if (inner && !isLoopNode(nid)) inner.remove();
            });
        } else {
            (subgraphRanges[id].nodes || []).forEach(function(nid) {
                var inner = graph.getCell(nid);
                if (inner) inner.remove();
            });
        }
        delete subgraphRanges[id];
    }
    graph.getConnectedLinks(cell).forEach(function(l) { l.remove(); });
    if (agentsData[id]) delete agentsData[id];
    cell.remove();
    return true;
}

function deleteSelected() {
    if (!selectedCell) return;
    if (!confirm('Delete selected?')) return;
    if (deleteCell(selectedCell)) {
        selectedCell = null;
        hidePropertyPanel();
        updateSubgraphContainerPositions();
        saveToHistory();
    }
}

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
    var items = [];
    if (selectedCell) {
        items.push({ label: 'Delete', icon: 'fa-trash', action: deleteSelected });
        items.push({ divider: true });
    }
    items.push(
        { label:'Create Agent', icon:'fa-robot', action: function() {
            var aid = prompt('Agent ID:') || 'agent_'+(++nodeCounter);
            if (!agentsData[aid]) agentsData[aid] = { id:aid, name:aid, type:'LLM', inputs:[], outputs:{ name:'output', type:'str' } };
            var el = createNode(aid); el.position(lp.x, lp.y); graph.addCell(el); saveToHistory();
        }},
        { label:'Create Branch', icon:'fa-code-branch', action: function() {
            var bid = 'branch_'+(++nodeCounter);
            agentsData[bid] = { id:bid, name:'Branch', type:'branch', inputs:['input'], outputs:{ name:'output', type:'dict' }, conditions:[{ label:'True', field:'', op:'not_empty', value:'' },{ label:'False', field:'', op:'empty', value:'' }] };
            var el = createNode(bid); el.position(lp.x, lp.y); graph.addCell(el); saveToHistory();
        }},
        { label:'Create Loop', icon:'fa-redo', action: function() {
            var lid = 'loop_' + (++nodeCounter);
            _addLoopAt(lid, lp, null);
        }},
        { divider:true },
        { label:'Export as SVG', icon:'fa-file-image', action: downloadSVG },
        { label:'Export as PNG', icon:'fa-image', action: downloadPNG },
        { label:'Export as TIFF (300 DPI)', icon:'fa-file-image', action: downloadTIFF },
        { divider:true },
        { label:'Fit to Content', icon:'fa-expand', action: fitToContent },
        { label:'Reset View', icon:'fa-sync', action: resetView }
    );
    showMenu(x, y, items);
}
function showNodeContextMenu(x, y, node) {
    var cfg = node.get('config') || {};
    var canDelete = node.id !== 'START' && node.id !== 'END';
    var items = [
        { label:'Node: '+(cfg.name||node.id), icon:'fa-cube', action: function(){} },
        { divider:true },
        { label:'Properties', icon:'fa-edit', action: function() { showPropertyPanel(node); } }
    ];
    if (canDelete) {
        items.push({ label:'Delete', icon:'fa-trash', action: function() {
            if (!confirm('Delete this node?')) return;
            if (deleteCell(node)) { deselectAll(); hidePropertyPanel(); updateSubgraphContainerPositions(); saveToHistory(); }
        }});
    }
    showMenu(x, y, items);
}
function showLinkContextMenu(x, y, link) {
    showMenu(x, y, [
        { label:'Delete', icon:'fa-trash', action: function() {
            if (!confirm('Delete this connection?')) return;
            if (deleteCell(link)) { deselectAll(); saveToHistory(); }
        }}
    ]);
}

// ─── Export (pure SVG nodes — foreignObject HTML does not rasterize) ───
var SVG_NS = 'http://www.w3.org/2000/svg';
var _EXPORT_FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';

function _svgEl(tag, attrs, text) {
    var el = document.createElementNS(SVG_NS, tag);
    if (attrs) {
        Object.keys(attrs).forEach(function(k) {
            el.setAttribute(k, attrs[k]);
        });
    }
    if (text != null) el.textContent = text;
    return el;
}

function _svgText(x, y, text, opts) {
    opts = opts || {};
    var t = _svgEl('text', {
        x: String(x),
        y: String(y),
        'font-family': _EXPORT_FONT,
        'font-size': String(opts.fontSize || 12),
        'font-weight': String(opts.fontWeight || 400),
        fill: opts.fill || '#374151',
        'text-anchor': opts.anchor || 'start'
    }, text);
    if (opts.fontStyle) t.setAttribute('font-style', opts.fontStyle);
    return t;
}

function _svgBadge(g, x, y, label, fill, stroke) {
    var w = Math.max(36, label.length * 6.2 + 14);
    g.appendChild(_svgEl('rect', {
        x: String(x), y: String(y), width: String(w), height: '18',
        rx: '4', ry: '4', fill: fill || 'rgba(255,255,255,0.22)',
        stroke: stroke || 'rgba(255,255,255,0.5)', 'stroke-width': '1'
    }));
    g.appendChild(_svgText(x + 7, y + 13, label, {
        fill: '#fff', fontSize: 10, fontWeight: 600
    }));
    return w;
}

function _exportNodeHeader(g, w, stroke, iconLetter, title, typeLabel) {
    g.appendChild(_svgEl('rect', {
        x: '0', y: '0', width: String(w), height: String(WF_HEADER_H),
        rx: '12', ry: '12', fill: stroke, stroke: 'none'
    }));
    g.appendChild(_svgEl('rect', {
        x: '0', y: String(WF_HEADER_H - 12), width: String(w), height: '12',
        fill: stroke, stroke: 'none'
    }));
    g.appendChild(_svgEl('rect', {
        x: '12', y: '9', width: '22', height: '22', rx: '6', ry: '6',
        fill: 'rgba(255,255,255,0.25)', stroke: 'rgba(255,255,255,0.7)', 'stroke-width': '1.5'
    }));
    g.appendChild(_svgText(23, 24, iconLetter, {
        fill: '#fff', fontSize: 11, fontWeight: 700, anchor: 'middle'
    }));
    g.appendChild(_svgText(42, 26, title, { fill: '#fff', fontSize: 13, fontWeight: 600 }));
    _svgBadge(g, w - 12 - Math.max(36, typeLabel.length * 6.2 + 14), 11, typeLabel);
}

function _exportIoSection(g, x, y, w, title, rows, dotColor) {
    g.appendChild(_svgText(x, y + 11, title, {
        fill: '#9ca3af', fontSize: 10, fontWeight: 700
    }));
    y += WF_IO_LABEL_H;
    if (!rows.length) {
        g.appendChild(_svgText(x + 12, y + 14, '—', {
            fill: '#d1d5db', fontSize: 11, fontStyle: 'italic'
        }));
        return y + WF_ROW_H;
    }
    rows.forEach(function(row) {
        g.appendChild(_svgEl('circle', {
            cx: String(x + 3), cy: String(y + 12), r: '3', fill: dotColor
        }));
        g.appendChild(_svgText(x + 12, y + 16, row.name, { fill: '#1f2937', fontSize: 12 }));
        if (row.type) {
            g.appendChild(_svgText(w - 12, y + 16, row.type, {
                fill: '#9ca3af', fontSize: 10, anchor: 'end'
            }));
        }
        y += WF_ROW_H;
    });
    return y;
}

/** Draw compound loop node (empty shell with inner list) as pure SVG. */
function _buildExportCompoundLoopSvg(cell, layout, agent) {
    var id = cell.id;
    var g = _svgEl('g', { class: 'export-node' });
    var w = layout.width;
    var h = layout.height;
    var stroke = layout.stroke;
    var name = truncateText((agent && agent.name) || id, 32);
    var lc = (agent && agent.loopConfig) || {};
    var loopType = lc.loopType || 'foreach';
    var inputs = normalizeInputs(agent);
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : 'output';

    g.appendChild(_svgEl('rect', {
        x: '0', y: '0', width: String(w), height: String(h),
        rx: '12', ry: '12', fill: '#ffffff', stroke: '#e5e7eb', 'stroke-width': '1.5'
    }));
    _exportNodeHeader(g, w, stroke, '↻', name, 'Loop');
    var y = WF_HEADER_H + 8;
    g.appendChild(_svgText(12, y + 11, 'Loop: ' + loopType, {
        fill: '#3b82f6', fontSize: 10, fontWeight: 600
    }));
    y += 18;
    var children = getLoopInnerDisplayNodes(id);
    if (!children.length) {
        g.appendChild(_svgEl('rect', {
            x: '12', y: String(y), width: String(w - 24), height: '40',
            rx: '8', ry: '8', fill: '#f8fafc', stroke: '#e2e8f0', 'stroke-width': '1'
        }));
        g.appendChild(_svgText(w / 2, y + 24, 'Drop agents or subgraphs here', {
            fill: '#94a3b8', fontSize: 11, anchor: 'middle'
        }));
        y += 48;
    } else {
        g.appendChild(_svgEl('rect', {
            x: '12', y: String(y), width: String(w - 24), height: String(children.length * 48 + 16),
            rx: '8', ry: '8', fill: '#f8fafc', stroke: '#e2e8f0', 'stroke-width': '1'
        }));
        children.forEach(function(ch, i) {
            var dt = ch.type === 'loop' ? 'loop' : ch.type;
            var chStroke = getNodeStroke(dt, false);
            var letter = typeIconLetters[dt] || ch.type.charAt(0) || '?';
            var cy = y + 12 + i * 48;
            g.appendChild(_svgEl('rect', {
                x: '20', y: String(cy + 6), width: '22', height: '22', rx: '6', ry: '6', fill: chStroke
            }));
            g.appendChild(_svgText(31, cy + 21, letter, {
                fill: '#fff', fontSize: 11, fontWeight: 700, anchor: 'middle'
            }));
            g.appendChild(_svgText(50, cy + 18, truncateText(ch.name, 28), {
                fill: '#1f2937', fontSize: 12, fontWeight: 600
            }));
            g.appendChild(_svgText(50, cy + 32, typeLabels[dt] || ch.type, {
                fill: '#9ca3af', fontSize: 10
            }));
        });
        y += children.length * 48 + 16 + 8;
    }
    y = _exportIoSection(g, 12, y, w, 'INPUT', inputs.map(function(inp) {
        return { name: truncateText(inp, 22) };
    }), '#3b82f6');
    y += WF_IO_BLOCK_GAP;
    _exportIoSection(g, 12, y, w, 'OUTPUT', [{ name: truncateText(outName, 20) }], '#10b981');
    return g;
}

/** Build a pure-SVG node group from the same layout data as the canvas HTML nodes. */
function buildExportNodeSvgGroup(cell) {
    var id = cell.id;
    if (id === 'START' || id === 'END' || id.endsWith('_container')) return null;
    if (cell.get('isLoopShell') || cell.get('subgraph')) return null;

    var agent = agentsData[id] || cell.get('config');
    if (!agent) return null;
    var layout = buildNodeLayout(id, agent);
    var rawType = (agent && agent.type) || 'LLM';
    var flowKind = (agent && agent.flowKind) || getNodeFlowKind(id) || '';
    if (!flowKind && (rawType === 'loop' || rawType === 'branch')) flowKind = rawType;
    var displayType = flowKind || rawType;
    if (displayType === 'loop' && !hasLoopInners(id)) {
        return _buildExportCompoundLoopSvg(cell, layout, agent);
    }

    var g = _svgEl('g', { class: 'export-node' });
    var w = layout.width;
    var h = layout.height;
    var stroke = layout.stroke;
    var type = (flowKind === 'loop' || flowKind === 'branch') ? flowKind : rawType;
    var name = truncateText((agent && agent.name) || id, 28);
    var inputs = normalizeInputs(agent);
    var outName = (agent && agent.outputs && agent.outputs.name) ? String(agent.outputs.name) : '';
    var outType = (agent && agent.outputs && agent.outputs.type) ? String(agent.outputs.type) : '';
    var model = (agent && agent.model) ? truncateText(agent.model, 32) : '';
    var tools = (agent && agent.tools) || [];
    var pinnedVersion = getPinnedAgentVersion(id) || '';
    var branchConds = (displayType === 'branch')
        ? ((agent && agent.conditions) || [{ label: 'True' }, { label: 'False' }])
        : [];
    var showIdRow = agent && agent.id && agent.name && agent.id !== agent.name;
    var iconLetter = typeIconLetters[displayType] || typeIconLetters[type] || type.charAt(0) || '?';
    var typeLabel = typeLabels[displayType] || typeLabels[type] || type;

    g.appendChild(_svgEl('rect', {
        x: '0', y: '0', width: String(w), height: String(h),
        rx: '12', ry: '12', fill: '#ffffff', stroke: '#e5e7eb', 'stroke-width': '1.5'
    }));
    _exportNodeHeader(g, w, stroke, iconLetter, name, typeLabel);

    var y = WF_HEADER_H + WF_BODY_PAD_TOP;
    if (showIdRow) {
        g.appendChild(_svgText(12, y + 11, truncateText(agent.id, 36), {
            fill: '#9ca3af', fontSize: 10
        }));
        y += WF_ID_ROW_H;
    }
    if (type === 'LLM' && model) {
        g.appendChild(_svgText(12, y + 11, 'Model: ' + model, { fill: '#6b7280', fontSize: 11 }));
        y += WF_META_LINE_H;
    } else if (type === 'PGM') {
        g.appendChild(_svgText(12, y + 11, 'Rule-based / Python', { fill: '#6b7280', fontSize: 11 }));
        y += WF_META_LINE_H;
    } else if (type === 'SUB') {
        g.appendChild(_svgText(12, y + 11, 'Iterates over list input', { fill: '#6b7280', fontSize: 11 }));
        y += WF_META_LINE_H;
    } else if (displayType === 'branch') {
        g.appendChild(_svgText(12, y + 11, 'Conditional routing (graph flow)', { fill: '#6b7280', fontSize: 11 }));
        y += WF_META_LINE_H;
    } else if (displayType === 'loop') {
        g.appendChild(_svgText(12, y + 11, 'Loop container (graph flow)', { fill: '#6b7280', fontSize: 11 }));
        y += WF_META_LINE_H;
    }
    if (pinnedVersion) {
        g.appendChild(_svgText(12, y + 11, 'Version: ' + pinnedVersion, {
            fill: '#1d4ed8', fontSize: 11, fontWeight: 600
        }));
        y += WF_META_LINE_H;
    }
    if (tools.length) {
        g.appendChild(_svgText(12, y + 11, 'Tools: ' + truncateText(tools.join(', '), 40), {
            fill: '#6b7280', fontSize: 11
        }));
        y += WF_META_LINE_H;
    }

    y = _exportIoSection(g, 12, y, w, 'INPUT', inputs.map(function(inp) {
        return { name: truncateText(inp, 22) };
    }), '#3b82f6');
    y += WF_IO_BLOCK_GAP;

    var outRows = [];
    if (displayType === 'branch' && branchConds.length) {
        branchConds.forEach(function(c) {
            outRows.push({ name: truncateText(c.label, 20), type: 'out' });
        });
    } else if (outName) {
        outRows.push({ name: truncateText(outName, 20), type: outType ? truncateText(outType, 8) : '' });
    }
    _exportIoSection(g, 12, y, w, 'OUTPUT', outRows, '#10b981');
    return g;
}

function _findExportElementRoot(svgRoot, cellId) {
    var hit = svgRoot.querySelector('.joint-element[model-id="' + cellId + '"]');
    if (hit) return hit;
    var all = svgRoot.querySelectorAll('.joint-element');
    for (var i = 0; i < all.length; i++) {
        if (all[i].getAttribute('model-id') === cellId) return all[i];
    }
    return null;
}

/** Replace foreignObject HTML nodes with pure SVG (works in canvg, Word, TIFF). */
function _replaceForeignObjectsWithPureSvg(svgRoot) {
    graph.getElements().forEach(function(cell) {
        var nodeG = buildExportNodeSvgGroup(cell);
        if (!nodeG) return;
        var elRoot = _findExportElementRoot(svgRoot, cell.id);
        if (!elRoot) return;
        elRoot.querySelectorAll('foreignObject').forEach(function(fo) { fo.remove(); });
        elRoot.querySelectorAll('[joint-selector="body"]').forEach(function(body) {
            body.setAttribute('visibility', 'hidden');
        });
        elRoot.insertBefore(nodeG, elRoot.firstChild);
    });
}

/** Bounding box of all graph content in model coordinates (respects manual drag layout). */
function _computeExportBBox(padding) {
    padding = padding == null ? 24 : padding;
    var bb = graph.getBBox();
    if (!bb) return { x: -padding, y: -padding, width: 400 + padding * 2, height: 300 + padding * 2 };
    graph.getElements().forEach(function(el) {
        var eb = el.getBBox();
        if (eb && eb.width && eb.height) bb = bb.union(eb);
    });
    return {
        x: bb.x - padding,
        y: bb.y - padding,
        width: bb.width + padding * 2,
        height: bb.height + padding * 2
    };
}

function _cleanExportSvg(svg) {
    svg.querySelectorAll('rect[fill]').forEach(function(r) {
        var fill = r.getAttribute('fill') || '';
        if (fill.indexOf('url(#') === 0 && fill.toLowerCase().indexOf('grid') >= 0) {
            r.setAttribute('fill', '#ffffff');
        }
    });
}

function _prepareExportSvg(bb) {
    var svg = paper.svg.cloneNode(true);
    _cleanExportSvg(svg);
    _replaceForeignObjectsWithPureSvg(svg);
    svg.setAttribute('viewBox', bb.x + ' ' + bb.y + ' ' + bb.width + ' ' + bb.height);
    svg.setAttribute('width', bb.width);
    svg.setAttribute('height', bb.height);
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
    return svg;
}

function _serializeExportSvg(svg) {
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(svg);
}

function _downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function() { URL.revokeObjectURL(url); }, 500);
}

async function _renderExportCanvas(scale) {
    var bb = _computeExportBBox();
    var svg = _prepareExportSvg(bb);
    var svgStr = _serializeExportSvg(svg);
    var w = Math.max(1, Math.round(bb.width * scale));
    var h = Math.max(1, Math.round(bb.height * scale));
    var canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);
    ctx.scale(scale, scale);
    if (typeof canvg !== 'undefined' && canvg.Canvg && canvg.Canvg.fromString) {
        var v = await canvg.Canvg.fromString(ctx, svgStr, { ignoreMouse: true, ignoreAnimation: true });
        await v.render();
    } else {
        await new Promise(function(resolve, reject) {
            var img = new Image();
            var url = URL.createObjectURL(new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' }));
            img.onload = function() {
                ctx.drawImage(img, 0, 0, bb.width, bb.height);
                URL.revokeObjectURL(url);
                resolve();
            };
            img.onerror = reject;
            img.src = url;
        });
    }
    return canvas;
}

function _withExportContext(fn) {
    var prev = selectedCell;
    deselectAll();
    return Promise.resolve(fn()).finally(function() {
        if (prev && prev.isElement && prev.isElement()) selectNode(prev);
        else if (prev && prev.isLink && prev.isLink()) selectLink(prev);
    });
}

function downloadSVG() {
    _withExportContext(function() {
        var bb = _computeExportBBox();
        var svg = _prepareExportSvg(bb);
        _downloadBlob(new Blob([_serializeExportSvg(svg)], { type: 'image/svg+xml;charset=utf-8' }),
            (current || 'workflow') + '.svg');
    });
}

function downloadPNG() {
    _withExportContext(async function() {
        var canvas = await _renderExportCanvas(2);
        canvas.toBlob(function(blob) {
            if (blob) _downloadBlob(blob, (current || 'workflow') + '.png');
        }, 'image/png');
    });
}

function downloadTIFF() {
    _withExportContext(async function() {
        var dpi = 300;
        var scale = dpi / 96;
        var canvas = await _renderExportCanvas(scale);
        if (typeof UTIF !== 'undefined' && UTIF.encodeImage) {
            var ctx = canvas.getContext('2d');
            var idata = ctx.getImageData(0, 0, canvas.width, canvas.height);
            var tiff = UTIF.encodeImage(idata.data, canvas.width, canvas.height);
            _downloadBlob(new Blob([tiff], { type: 'image/tiff' }), (current || 'workflow') + '_300dpi.tiff');
        } else {
            canvas.toBlob(function(blob) {
                if (blob) _downloadBlob(blob, (current || 'workflow') + '_300dpi.png');
            }, 'image/png');
        }
    });
}

// ─── Save / serialize ──────────────────────────────
function saveGraph() {
    var wd = serializeGraph(); wd.id = current || prompt('Workflow ID:') || 'new_workflow'; wd.name = $('#currentWorkflowName').text();
    if (!wd.id) return alert('ID required');
    $.ajax({ url:'/graph/api/save', method:'POST', contentType:'application/json', data: JSON.stringify(wd), success: function(r) { alert(r.success?'Saved!':'Failed: '+(r.error||'Unknown')); }, error: function(x) { alert('Error: '+(x.responseJSON?x.responseJSON.error:x.statusText)); } });
}
function serializeGraph() {
    syncCurrentGraphFromCanvas();
    if (selectedCell && selectedCell.isElement()) {
        var sc = selectedCell.get('config') || {};
        var sid = sc.id || selectedCell.id;
        if (sc.flowKind === 'loop' || sc.type === 'loop') syncLoopPanelToAgent(sid);
    }
    var wf = currentGraph ? JSON.parse(JSON.stringify(currentGraph)) : {
        nodes: ['START', 'END'],
        edges: [['START', 'END']],
        flowNodes: {},
        bindings: {},
        agentVersions: {}
    };
    wf.flowNodes = JSON.parse(JSON.stringify((currentGraph && currentGraph.flowNodes) || {}));
    wf.bindings = JSON.parse(JSON.stringify(getGraphBindings(currentGraph) || {}));
    wf.agentVersions = JSON.parse(JSON.stringify(getGraphAgentVersions(currentGraph) || {}));
    wf.name = $('#currentWorkflowName').text() || wf.name || '';
    if (!wf.nodes || !wf.nodes.length) {
        wf.nodes = ['START', 'END'];
    }
    if (!wf.edges || !wf.edges.length) {
        wf.edges = [['START', 'END']];
    }
    persistCanvasLayoutToGraph(wf);
    return wf;
}

// ─── Test ───────────────────────────────────────────
var _lastTestGraphId = null;

function _hasTestSample(obj) {
    return obj && typeof obj === 'object' && Object.keys(obj).length > 0;
}

function _applyTestInputSample(sample) {
    if (_hasTestSample(sample)) {
        $('#testInput').val(JSON.stringify(sample, null, 2));
    } else {
        $('#testInput').val('');
    }
}

function _loadWorkflowTestSample(graphId, done) {
    if (_hasTestSample(workflowTestDefault)) {
        done(workflowTestDefault);
        return;
    }
    fetch('/graph/api/test-default/' + encodeURIComponent(graphId))
        .then(function(r) { return r.json(); })
        .then(function(data) { done(_hasTestSample(data) ? data : null); })
        .catch(function() { done(null); });
}

function openTestModal() {
    var graphId = current;
    if (!graphId) {
        alert('Save the workflow first (workflow ID required).');
        return;
    }
    function showModal() {
        new bootstrap.Modal('#testModal').show();
    }
    if ($('#testInput').val().trim() && _lastTestGraphId === graphId) {
        showModal();
        return;
    }
    _loadWorkflowTestSample(graphId, function(sample) {
        _applyTestInputSample(sample);
        _lastTestGraphId = graphId;
        showModal();
    });
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
    Object.keys(input).forEach(function(k) {
        var v = input[k];
        if (v !== null && typeof v === 'object') {
            params.set(k, JSON.stringify(v));
        } else if (v !== undefined && v !== null) {
            params.set(k, String(v));
        }
    });
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
        if (chunk.indexOf('ner_llm') >= 0 && (chunk.indexOf('entities') >= 0 || chunk.indexOf('Chemical') >= 0)) {
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
