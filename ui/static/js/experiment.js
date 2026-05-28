function renderTestset(data){
    const $datasetSelect = $('#datasetSelect');
    $datasetSelect.empty();
    if (data) {
        data.forEach(f => {
            const selected = f.name === defaultFilename ? 'selected' : '';
            $datasetSelect.append(
                `<option value="${f.name}" ${selected} data-samples="${f.count}">${f.name} (${f.count} samples)</option>`
            );
        });

        if (defaultFilename && $datasetSelect.find(`option[value="${defaultFilename}"]`).length) {
            $('#runExpBtn').removeClass('d-none').show();
        }
    }
}

$(document).ready(function () {
    const runnerId = $('#runnerId');
    const runnerType = $('#runnerType');
    const datasetSelect = $('#datasetSelect');
    renderTestset(data);
    updateProgress(progress || 0);

    const observer = new MutationObserver(function () {
        const id = runnerId.val();
        if (!id) {
            return;
        }

        $.getJSON(`/testset/api/by_agent/${id}`)
            .done(function(data) {
                const lite = (data || []).map((t) => ({
                    name: t.name,
                    count: t.count,
                }));
                renderTestset(lite);
            })
            .fail(function() {
                datasetSelect.html('<option value="">-- Error loading test sets --</option>');
            });
    });

    observer.observe(runnerType[0], {attributes: true, childList: true, subtree: true});
    observer.observe(runnerId[0], {attributes: true, childList: true, subtree: true});

    /* ========= 事件绑定（jQuery 写法） ========= */
     $(document).on('click', '.btn-replay', function () {
        const idx = $(this).data('index');   // 拿到当前行 id
         $('#idx').text(idx);          // 清空
         $('#replayPopup').removeClass('hidden');
         const jsonStr = JSON.stringify(snapShots[idx], null, 2);   // 2 个空格缩进
          const $out    = $('#resultOutput');
          $out.text(jsonStr);                // 先放纯文本
          Prism.highlightElement($out[0]);   // 让 Prism 上色
      });

     /* ====== 关闭 run-runner 弹窗 ====== */
    $(document).on('click', '.replay-popup .close-btn', () => {
        $('#replayPopup').addClass('hidden');
        $('#idx').val('');          // 清空
        $('#resultOutput').empty();
    });

    $(document).on('shown.bs.tab', 'a[data-bs-toggle="tab"]', function (e) {
        const paneId = $(e.target).attr('href');
        const id = $('#exp_id').attr('data-id') || $('#exp_id').data('id') || expId;
        const prog = parseInt($('#overallProgress').text(), 10) || progress;
        if (paneId === '#report' && id && id !== 'Not saved yet' && (prog >= 100 || $('#overallProgress').width() > 0)) {
            renderReport(id);
        }
    });
});

function renderTable(file){
    const runnerId = $('#runnerId').val();
    const runnerType = $('#runnerType').val();
    const runnerDisplay = $('#runnerDisplay').val();
    if (file && runnerId) {
        // 直接跳转，带参数刷新页面
        const params = new URLSearchParams({
            runner_id: runnerId,
            runner_type: runnerType,
            runner_display: runnerDisplay,
            filename: file
        });
        window.location.href = `/exp/new?${params.toString()}`;
    }else{
        $('#runExpBtn').addClass('d-none').hide();  // 隐藏
    }

}

// 当选择 testset 文件时 → 加载分页数据预览表
$('#datasetSelect').change(function () {
    renderTable($(this).val());
});
/* ====== 提交运行 ====== */
$('#expForm').submit(function (e) {
    e.preventDefault();
    /* 1. 收集可编辑字段 */
    const formData = {
        dataset: $('#datasetSelect').val(),
        runner_type: $('#runnerType').val(),
        runner_id: $('#runnerId').val(),
        runner_display: $('#runnerDisplay').val(),
        samples: $('#datasetSelect').find(':selected').data('samples') || 0,
        exp_id: $('#exp_id').data('id')
    };

    // 简单校验
    if (!formData.runner_id || !formData.dataset) {
        alert('Please select Runner and Dataset');
        return;
    }
    $('#runExpBtn').addClass('d-none').hide();  // 隐藏
    // 2. POST 到后端保存接口
    $.ajax({
        url: '/exp/api/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function (resp) {
            if (resp.success) {
                $('#exp_id').text(resp.exp_id);
                $('#exp_id').data('id', resp.exp_id);
                //start stream
                start_task(resp.exp_id);
            } else {
                alert('Save Failed: ' + (resp.error || 'unknown error'));
            }
        },
        error: function (xhr) {
            console.error(xhr);
            alert('Request failed: ' + xhr.status + ' ' + xhr.statusText);
        }
    });


});



function start_task(exp_id){
    $.ajax({
        url: `/exp/api/update`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ "exp_id": exp_id, "status": "running" ,"progress": 0}),
        success: function (resp) {
            if (resp.success) {
                //start stream
                stream(exp_id);
            } else {
                alert('Save Failed: ' + (resp.error || 'unknown error'));
            }
        },
        error: function (xhr) {
            console.error(xhr);
            alert('Request failed: ' + xhr.status + ' ' + xhr.statusText);
        }
    });
}

function complete_task(exp_id,progress,status){
    if(status!=='failed'){
        status='completed';
    }
    $.ajax({
        url: `/exp/api/update`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ "exp_id": exp_id, "status":status,"progress":progress }),
        success: function (resp) {
            if (resp.success) {
                window.location.href = `/exp/${exp_id}`;
            } else {
                alert('Save Failed: ' + (resp.error || 'unknown error'));
            }
        },
        error: function (xhr) {
            console.error(xhr);
            alert('Request failed: ' + xhr.status + ' ' + xhr.statusText);
        }
    });
}


const statusConfig = {
    'completed': {
        text: 'Completed',
        class: 'badge text-bg-success'
    },
    'running': {
        text: 'Running',
        class: 'badge text-bg-primary'
    },
    'pending': {
        text: 'Pending',
        class: 'badge text-bg-warning'
    },
    'failed': {
        text: 'Failed',
        class: 'badge text-bg-danger'
    }
};
// 辅助函数：更新表格中单行 status
function updateTableRow(index, data) {
    const $row = $(`#paged_table tbody tr:nth-child(${index})`);
    for (const [key, value] of Object.entries(data)) {
        // 1. 在表头中查找对应的列
        let colIndex = -1;

        // 方法A：通过表头文本匹配
        $(`#paged_table thead th`).each(function(i) {
            const headerText = $(this).text().trim().toLowerCase();
            if (headerText === key.toLowerCase()) {
                colIndex = i;
                return false; // 退出循环
            }
        });


        // 2. 如果找到对应的列，更新单元格
        if (colIndex !== -1) {
            const $cell = $row.find(`td:eq(${colIndex})`);
            if (key === 'status') {
                const statusInfo = statusConfig[value.toLowerCase()] || statusConfig.pending;
                // 生成带CSS类的HTML
                const statusHtml = `<span class="${statusInfo.class}">${statusInfo.text}</span>`;

                // 更新单元格内容
                $cell.html(statusHtml);
            }else {
                $cell.text(value);
            }
        } else {
            console.warn(`Column "${key}" not found in table header`);
        }

    }
}
// 辅助函数：更新整体进度条
function updateProgress(percent) {
    const width = percent ;
    $('#overallProgress')
        .css('width', width + '%')
        .text(width + '%')
        .toggleClass('progress-bar-animated', width < 100);
}

function freezeInputAndLink(){
    $('#datasetSelect').prop('disabled', true);
    $('#runnerSearch').prop('disabled', true);
    $('#expTab').css({'pointer-events':'none', 'opacity':'0.6'});
    $('#pageNav').css({'pointer-events':'none', 'opacity':'0.6'});
}



function stream(exp_id){
    let current_process=0;
    let current_status='pending';
    let reconnectCount = 0;
    const maxReconnect = 2;
        /* 4. 关闭旧连接 */
    updateProgress(current_process);
    freezeInputAndLink();
    window.agentEventSource?.close();

    function openStream() {
        window.agentEventSource?.close();
        window.agentEventSource = new EventSource(`/stream/run/${exp_id}`);
        window.agentEventSource.onmessage = e => {
            if (e.data === '[DONE]') {
                window.agentEventSource.close();
                complete_task(exp_id,current_process,current_status)
                return;
            }
            try {
                const msg = JSON.parse(e.data);  // 后端推 JSON 更灵活
                if(msg.status==='failed'){
                   $('#error_message').text(msg.error);
                   current_status='failed';
                   updateTableRow(msg.current_index, {"status": "failed"});
                }else{
                    current_status = msg.batch_status || msg.status;
                    current_process=msg.percent;
                    updateProgress(current_process);
                    updateTableRow(msg.current_index, {"status": msg.status});
                }
            } catch (err) {
               console.error('SSE parse error:', err);
            }
        };
        window.agentEventSource.onerror = err => {
            console.error('SSE error:', err);
            window.agentEventSource.close();
            // Flask debug auto-reload can temporarily reset SSE; try reconnect.
            if (reconnectCount < maxReconnect) {
                reconnectCount += 1;
                $('#error_message').text(`SSE reconnected (${reconnectCount}/${maxReconnect})...`);
                setTimeout(openStream, 1200);
                return;
            }
            $('#error_message').text('SSE disconnected. Please retry run.');
            $('#runExpBtn').removeClass('d-none').show();  // 显示
        };
    }

    /* 6. 新开 SSE */
    openStream();
}



function disposeReportCharts() {
    if (window.reportOverallChartInstance) {
        window.reportOverallChartInstance.dispose();
        window.reportOverallChartInstance = null;
    }
    if (window.reportSampleChartInstance) {
        window.reportSampleChartInstance.dispose();
        window.reportSampleChartInstance = null;
    }
    if (window.reportErrorBucketChartInstance) {
        window.reportErrorBucketChartInstance.dispose();
        window.reportErrorBucketChartInstance = null;
    }
    if (window.reportAgentImpactChartInstance) {
        window.reportAgentImpactChartInstance.dispose();
        window.reportAgentImpactChartInstance = null;
    }
}

function renderReportCharts(chartData) {
    const root = $('#reportMarkdown');
    if (!chartData || Number(chartData.sample_count || 0) <= 0 || !root.length) {
        disposeReportCharts();
        root.find('.report-inline-chart-card').remove();
        return;
    }
    const ensureSlot = (slotId, title, headingRegex) => {
        let $slot = $(`#${slotId}`);
        if ($slot.length) return $slot;
        const blockHtml = `
          <div class="report-inline-chart-card" data-slot="${slotId}">
            <div class="small text-muted mb-2">${title}</div>
            <div id="${slotId}" class="report-inline-chart-canvas"></div>
          </div>
        `;
        const headings = root.find('h2, h3');
        let inserted = false;
        headings.each(function () {
            const txt = ($(this).text() || '').toLowerCase();
            if (headingRegex.test(txt)) {
                $(this).after(blockHtml);
                inserted = true;
                return false;
            }
            return true;
        });
        if (!inserted) {
            root.append(blockHtml);
        }
        $slot = $(`#${slotId}`);
        return $slot;
    };

    const sampleSlot = ensureSlot('reportSampleChartInline', 'Per-sample F1 Trend', /metrics/);
    const errorSlot = ensureSlot('reportErrorBucketChartInline', 'FN/FP Composition', /(fn|fp|false negative|false positive)/);
    const impactSlot = ensureSlot('reportAgentImpactChartInline', 'Agent Version Impact (F1 Delta)', /(suggestion|agent modification)/);

    const perSample = Array.isArray(chartData.per_sample) ? chartData.per_sample : [];
    const xLabels = perSample.map((x) => String(x.sample_id));
    const f1Values = perSample.map((x) => Number(x.f1 || 0));
    const pValues = perSample.map((x) => Number(x.precision || 0));
    const rValues = perSample.map((x) => Number(x.recall || 0));
    const sampleDom = sampleSlot.get(0);
    const errorDom = errorSlot.get(0);
    const impactDom = impactSlot.get(0);
    if (!sampleDom || !errorDom || !impactDom || typeof echarts === 'undefined') {
        return;
    }
    disposeReportCharts();
    window.reportSampleChartInstance = echarts.init(sampleDom);
    window.reportSampleChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['F1', 'Precision', 'Recall'] },
        grid: { left: 45, right: 16, top: 30, bottom: 40 },
        xAxis: {
            type: 'category',
            data: xLabels,
            name: 'Sample',
            nameLocation: 'middle',
            nameGap: 28
        },
        yAxis: { type: 'value', min: 0, max: 1 },
        series: [
            { name: 'F1', type: 'line', smooth: true, data: f1Values },
            { name: 'Precision', type: 'line', smooth: true, data: pValues },
            { name: 'Recall', type: 'line', smooth: true, data: rValues }
        ]
    });

    const err = chartData.error_buckets || {};
    window.reportErrorBucketChartInstance = echarts.init(errorDom);
    window.reportErrorBucketChartInstance.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
            name: 'Error Buckets',
            type: 'pie',
            radius: ['42%', '70%'],
            avoidLabelOverlap: true,
            data: [
                { name: 'TP', value: Number(err.rel_tp || 0), itemStyle: { color: '#22c55e' } },
                { name: 'FP', value: Number(err.rel_fp || 0), itemStyle: { color: '#ec4899' } },
                { name: 'FN', value: Number(err.rel_fn || 0), itemStyle: { color: '#facc15' } }
            ],
            label: { formatter: '{b}: {c}' }
        }]
    });

    const impacts = Array.isArray(chartData.agent_version_impact) ? chartData.agent_version_impact : [];
    const topImpacts = impacts.slice(0, 8);
    const agentNames = topImpacts.map((x) => String(x.agent_id || 'unknown'));
    const bestDeltas = topImpacts.map((x) => Number(x.best_f1_delta || 0));
    const acceptedRounds = topImpacts.map((x) => Number(x.accepted_rounds || 0));
    window.reportAgentImpactChartInstance = echarts.init(impactDom);
    window.reportAgentImpactChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['Best F1 Delta', 'Accepted Rounds'] },
        grid: { left: 100, right: 16, top: 30, bottom: 24 },
        xAxis: [
            { type: 'value', name: 'Best F1 Delta' },
            { type: 'value', name: 'Accepted', min: 0 }
        ],
        yAxis: { type: 'category', data: agentNames },
        series: [
            {
                name: 'Best F1 Delta',
                type: 'bar',
                data: bestDeltas,
                xAxisIndex: 0
            },
            {
                name: 'Accepted Rounds',
                type: 'bar',
                data: acceptedRounds,
                xAxisIndex: 1
            }
        ]
    });
    setTimeout(() => {
        window.reportSampleChartInstance?.resize();
        window.reportErrorBucketChartInstance?.resize();
        window.reportAgentImpactChartInstance?.resize();
    }, 50);
}

function styleReportTables(root) {
    root.find('table').each(function () {
        const $table = $(this);
        if (!$table.parent().hasClass('report-table-wrap')) {
            $table.wrap('<div class="report-table-wrap"></div>');
        }
        $table.addClass('report-table table table-striped table-hover table-sm align-middle mb-0');
    });
}

function colorSuggestionPlusMinus(root) {
    const headers = root.find('h2, h3');
    let $start = null;
    headers.each(function () {
        const t = ($(this).text() || '').toLowerCase();
        if (t.includes('agent modification suggestions')) {
            $start = $(this);
            return false;
        }
        return true;
    });
    if (!$start || !$start.length) return;

    const $sectionNodes = $start.nextUntil('h2');
    $sectionNodes.find('p, li').each(function () {
        const walker = document.createTreeWalker(this, NodeFilter.SHOW_TEXT, null);
        const textNodes = [];
        let node = walker.nextNode();
        while (node) {
            textNodes.push(node);
            node = walker.nextNode();
        }
        textNodes.forEach((n) => {
            const txt = n.nodeValue || '';
            if (!/[+-]/.test(txt)) return;
            const html = txt
                .replace(/(^|[\s(])\+(?=[\s):,;]|$)/g, '$1<span class="suggest-plus">+</span>')
                .replace(/(^|[\s(])-(?=[\s):,;]|$)/g, '$1<span class="suggest-minus">-</span>');
            if (html === txt) return;
            const span = document.createElement('span');
            span.innerHTML = html;
            n.parentNode.replaceChild(span, n);
        });
    });
}

function enhanceReportMarkup() {
    const root = $('#reportMarkdown');
    if (!root.length) return;
    styleReportTables(root);
    colorSuggestionPlusMinus(root);
}

function loadAndRenderReportCharts(expIdVal) {
    return $.getJSON(`/exp/api/${encodeURIComponent(expIdVal)}/report-charts`)
        .done((payload) => {
            renderReportCharts(payload || {});
        })
        .fail(() => {
            disposeReportCharts();
            $('#reportMarkdown').find('.report-inline-chart-card').remove();
        });
}

function renderReport(exp_id) {
    setOptimizeLoopControlsEnabled(false);
    disposeReportCharts();
    $('#reportMarkdown').html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Make report...');
    window.agentEventSource?.close();
    let buffer = '';
    const useTools = $('#reportToolsMode').is(':checked');
    const params = new URLSearchParams({ use_tools: useTools ? '1' : '0' });
    window.agentEventSource = new EventSource(`/stream/report/${encodeURIComponent(exp_id)}?${params.toString()}`);
    window.agentEventSource.onmessage = e => {
        if (e.data === '[DONE]') {
            $('#reportMarkdown').html(marked.parse(buffer));
            enhanceReportMarkup();
            loadAndRenderReportCharts(exp_id);
            window.agentEventSource.close();
            setOptimizeLoopControlsEnabled(true);
            return;
        }
        buffer += e.data.replace(/\\n/g, '\n');
        if (buffer.trim()) {
            $('#reportMarkdown').html(marked.parse(buffer));
            enhanceReportMarkup();
        }
    };
    window.agentEventSource.onerror = err => {
        console.error('SSE error:', err);
        window.agentEventSource.close();
        setOptimizeLoopControlsEnabled(true);
        disposeReportCharts();
        $('#reportMarkdown').find('.report-inline-chart-card').remove();
        if (!buffer.trim()) {
            $('#reportMarkdown').html(
                '<p class="text-danger">Report failed. Ensure <code>result/' +
                escHtml(exp_id) + '/states.json</code> exists and the experiment status is completed.</p>'
            );
        }
    };
}

function escHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function setOptimizeLoopControlsEnabled(enabled) {
    $('#optimizeLoopBtn').prop('disabled', !enabled);
}

function disposeOptimizeSummaryCharts() {
    if (window.optimizeRoundDeltaChartInstance) {
        window.optimizeRoundDeltaChartInstance.dispose();
        window.optimizeRoundDeltaChartInstance = null;
    }
    if (window.optimizeStatusPieChartInstance) {
        window.optimizeStatusPieChartInstance.dispose();
        window.optimizeStatusPieChartInstance = null;
    }
}

function _optStatusBadge(r) {
    if (r.accepted) return '<span class="badge text-bg-success">Accepted</span>';
    if (r.status === 'skipped') return '<span class="badge text-bg-secondary">Skipped</span>';
    return '<span class="badge text-bg-warning text-dark">Retained Baseline</span>';
}

function _fmtDelta(v) {
    const n = Number(v || 0);
    const cls = n > 0 ? 'text-success' : (n < 0 ? 'text-danger' : 'text-muted');
    const sign = n > 0 ? '+' : '';
    return `<span class="${cls} fw-semibold">${sign}${n.toFixed(4)}</span>`;
}

function renderOptimizeSummary(summary) {
    if (!summary) return '';
    const base = summary.baseline_exp_id || '';
    const finalBest = summary.final_best_exp_id || '';
    const finalGraph = summary.final_graph_id || '';
    const finalMetrics = summary.final_best_metrics || {};
    const rounds = Array.isArray(summary.rounds) ? summary.rounds : [];
    const verMap = summary.accepted_version_map || {};
    const acceptedCount = rounds.filter((r) => r && r.accepted).length;
    const versions = Object.keys(verMap).length
        ? Object.entries(verMap).map(([k, v]) => `
            <tr>
              <td><code>${escHtml(k)}</code></td>
              <td><code>${escHtml(v)}</code></td>
            </tr>
          `).join('')
        : '<tr><td colspan="2" class="text-muted">No accepted version changes.</td></tr>';
    const roundRows = rounds.length
        ? rounds.map((r) => {
            const del = r.metrics_delta || {};
            const vm = r.version_map || {};
            const vmText = Object.keys(vm).length
                ? Object.entries(vm).map(([k, v]) => `${escHtml(k)} → ${escHtml(v)}`).join(', ')
                : '-';
            return `
              <tr>
                <td>${Number(r.round || 0)}</td>
                <td><code>${escHtml(r.target_agent_id || '-')}</code></td>
                <td>${(r.display_exp_id || r.candidate_exp_id) ? `<a href="/exp/${encodeURIComponent(r.display_exp_id || r.candidate_exp_id)}" target="_blank" rel="noopener"><code>${escHtml(r.display_exp_id || r.candidate_exp_id)}</code></a>` : '<span class="text-muted">-</span>'}</td>
                <td>${_fmtDelta(del.precision)}</td>
                <td>${_fmtDelta(del.recall)}</td>
                <td>${_fmtDelta(del.f1)}</td>
                <td>${_optStatusBadge(r)}</td>
                <td class="small text-muted">${escHtml(r.reason || '-')}</td>
                <td class="small">${escHtml(vmText)}</td>
              </tr>
            `;
        }).join('')
        : '<tr><td colspan="9" class="text-muted">No actionable suggestions found.</td></tr>';
    return `
      <div class="card optimize-summary-card">
        <div class="card-header"><strong>Optimize Loop Result</strong></div>
        <div class="card-body">
          <div class="opt-kpi-grid mb-3">
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Baseline</div>
              <div class="opt-kpi-value"><a href="/exp/${encodeURIComponent(base)}" target="_blank" rel="noopener"><code>${escHtml(base || '-')}</code></a></div>
            </div>
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Final Best</div>
              <div class="opt-kpi-value"><a href="/exp/${encodeURIComponent(finalBest)}" target="_blank" rel="noopener"><code>${escHtml(finalBest || '-')}</code></a></div>
            </div>
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Final Graph</div>
              <div class="opt-kpi-value"><code>${escHtml(finalGraph || '-')}</code></div>
            </div>
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Suggestion Count</div>
              <div class="opt-kpi-value">${Number(summary.suggestion_count || 0)}</div>
            </div>
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Accepted Rounds</div>
              <div class="opt-kpi-value text-success">${acceptedCount}</div>
            </div>
          </div>

          <div class="report-table-wrap mb-3">
            <table class="report-table table table-striped table-hover table-sm align-middle mb-0">
              <thead>
                <tr><th>Final Metric</th><th>Value</th></tr>
              </thead>
              <tbody>
                <tr><td>Precision</td><td>${Number(finalMetrics.precision || 0).toFixed(4)}</td></tr>
                <tr><td>Recall</td><td>${Number(finalMetrics.recall || 0).toFixed(4)}</td></tr>
                <tr><td>F1</td><td>${Number(finalMetrics.f1 || 0).toFixed(4)}</td></tr>
              </tbody>
            </table>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-md-8">
              <div class="report-inline-chart-card mb-0">
                <div class="small text-muted mb-2">Round F1 Delta</div>
                <div id="optRoundDeltaChart" class="report-inline-chart-canvas"></div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="report-inline-chart-card mb-0">
                <div class="small text-muted mb-2">Round Status Composition</div>
                <div id="optStatusPieChart" class="report-inline-chart-canvas"></div>
              </div>
            </div>
          </div>

          <div class="report-table-wrap mb-3">
            <table class="report-table table table-striped table-hover table-sm align-middle mb-0">
              <thead>
                <tr><th>Agent</th><th>Accepted Version</th></tr>
              </thead>
              <tbody>${versions}</tbody>
            </table>
          </div>

          <div class="report-table-wrap">
            <table class="report-table table table-striped table-hover table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>Round</th><th>Agent</th><th>Candidate Exp</th>
                  <th>ΔPrecision</th><th>ΔRecall</th><th>ΔF1</th>
                  <th>Status</th><th>Reason</th><th>Version Map</th>
                </tr>
              </thead>
              <tbody>${roundRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
}

function renderOptimizeSummaryCharts(summary) {
    if (typeof echarts === 'undefined') return;
    const rounds = Array.isArray(summary?.rounds) ? summary.rounds : [];
    const roundDom = document.getElementById('optRoundDeltaChart');
    const pieDom = document.getElementById('optStatusPieChart');
    if (!roundDom || !pieDom) return;
    disposeOptimizeSummaryCharts();

    const x = rounds.map((r) => `R${Number(r.round || 0)}`);
    const f1 = rounds.map((r) => Number((r.metrics_delta || {}).f1 || 0));
    const colors = rounds.map((r) => (r.accepted ? '#22c55e' : (r.status === 'skipped' ? '#94a3b8' : '#f59e0b')));
    window.optimizeRoundDeltaChartInstance = echarts.init(roundDom);
    window.optimizeRoundDeltaChartInstance.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 45, right: 12, top: 24, bottom: 30 },
        xAxis: { type: 'category', data: x },
        yAxis: { type: 'value', name: 'ΔF1' },
        series: [{
            type: 'bar',
            data: f1.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
            label: { show: true, position: 'top', formatter: (p) => Number(p.value || 0).toFixed(4) }
        }]
    });

    const accepted = rounds.filter((r) => r && r.accepted).length;
    const skipped = rounds.filter((r) => r && r.status === 'skipped').length;
    const retained = Math.max(0, rounds.length - accepted - skipped);
    window.optimizeStatusPieChartInstance = echarts.init(pieDom);
    window.optimizeStatusPieChartInstance.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [{
            type: 'pie',
            radius: ['44%', '72%'],
            data: [
                { name: 'Accepted', value: accepted, itemStyle: { color: '#22c55e' } },
                { name: 'Retained Baseline', value: retained, itemStyle: { color: '#f59e0b' } },
                { name: 'Skipped', value: skipped, itemStyle: { color: '#94a3b8' } }
            ],
            label: { formatter: '{b}: {c}' }
        }]
    });
    setTimeout(() => {
        window.optimizeRoundDeltaChartInstance?.resize();
        window.optimizeStatusPieChartInstance?.resize();
    }, 60);
}

$('#optimizeLoopBtn').on('click', function () {
    const expIdVal = $('#exp_id').attr('data-id') || $('#exp_id').data('id') || expId;
    if (!expIdVal || expIdVal === 'Not saved yet') {
        alert('Please run and save an experiment first.');
        return;
    }
    const $btn = $(this);
    if (window.optimizeLoopSource) {
        window.optimizeLoopSource.close();
        window.optimizeLoopSource = null;
    }
    $btn.prop('disabled', true);
    $('#optimizeLoopStatus').text('Starting optimize loop...');
    $('#optimizeLoopProgress').css('width', '0%').text('0%').addClass('progress-bar-animated progress-bar-striped');
    $('#optimizeLoopResult').html('');
    disposeOptimizeSummaryCharts();
    $.ajax({
        url: '/exp/api/optimize-loop/start',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ exp_id: expIdVal }),
        success: function (resp) {
            if (!resp.success) {
                $('#optimizeLoopStatus').text('Failed');
                alert(resp.error || 'Optimize loop failed');
                $btn.prop('disabled', false);
                return;
            }
            const taskId = resp.task_id;
            const es = new EventSource(`/exp/stream/optimize-loop/${encodeURIComponent(taskId)}`);
            window.optimizeLoopSource = es;
            es.onmessage = function (e) {
                if (e.data === '[DONE]') {
                    es.close();
                    $btn.prop('disabled', false);
                    $('#optimizeLoopProgress').removeClass('progress-bar-animated progress-bar-striped');
                    return;
                }
                let msg = {};
                try {
                    msg = JSON.parse(e.data);
                } catch (_err) {
                    return;
                }
                const p = Math.max(0, Math.min(100, Number(msg.progress || 0)));
                $('#optimizeLoopProgress').css('width', `${p}%`).text(`${p}%`);
                $('#optimizeLoopStatus').text(`${msg.stage || 'running'}: ${msg.message || ''}`);
                if (msg.status === 'failed') {
                    $('#optimizeLoopStatus').text(`Failed: ${msg.error || 'unknown error'}`);
                    $('#optimizeLoopProgress').removeClass('progress-bar-animated progress-bar-striped');
                    es.close();
                    $btn.prop('disabled', false);
                }
                if (msg.summary) {
                    $('#optimizeLoopResult').html(renderOptimizeSummary(msg.summary));
                    renderOptimizeSummaryCharts(msg.summary);
                }
            };
            es.onerror = function () {
                $('#optimizeLoopStatus').text('Stream disconnected');
                $('#optimizeLoopProgress').removeClass('progress-bar-animated progress-bar-striped');
                es.close();
                $btn.prop('disabled', false);
            };
        },
        error: function (xhr) {
            $('#optimizeLoopStatus').text('Failed');
            alert((xhr.responseJSON && xhr.responseJSON.error) || 'Optimize loop request failed');
            $btn.prop('disabled', false);
        }
    });
});