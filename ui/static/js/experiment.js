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



function renderReport(exp_id) {
    setOptimizeLoopControlsEnabled(false);
    $('#reportMarkdown').html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Make report...');
    window.agentEventSource?.close();
    let buffer = '';
    window.agentEventSource = new EventSource(`/stream/report/${encodeURIComponent(exp_id)}`);
    window.agentEventSource.onmessage = e => {
        if (e.data === '[DONE]') {
            $('#reportMarkdown').html(marked.parse(buffer));
            window.agentEventSource.close();
            setOptimizeLoopControlsEnabled(true);
            return;
        }
        buffer += e.data.replace(/\\n/g, '\n');
        if (buffer.trim()) {
            $('#reportMarkdown').html(marked.parse(buffer));
        }
    };
    window.agentEventSource.onerror = err => {
        console.error('SSE error:', err);
        window.agentEventSource.close();
        setOptimizeLoopControlsEnabled(true);
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

function renderOptimizeSummary(summary) {
    if (!summary) return '';
    const base = summary.baseline_exp_id || '';
    const finalBest = summary.final_best_exp_id || '';
    const rounds = Array.isArray(summary.rounds) ? summary.rounds : [];
    const verMap = summary.accepted_version_map || {};
    const versions = Object.keys(verMap).length
        ? Object.entries(verMap).map(([k, v]) => `<li><code>${escHtml(k)}</code> -> <code>${escHtml(v)}</code></li>`).join('')
        : '<li>No accepted version changes.</li>';
    const roundHtml = rounds.length
        ? rounds.map((r) => {
            const del = r.metrics_delta || {};
            const vm = r.version_map || {};
            const vmText = Object.keys(vm).length
                ? Object.entries(vm).map(([k, v]) => `<code>${escHtml(k)}</code> -> <code>${escHtml(v)}</code>`).join(', ')
                : 'No version accepted';
            const verdict = r.accepted ? 'Accepted' : (r.status === 'skipped' ? 'Skipped' : 'Baseline retained');
            const cmp = r.llm_compare
                ? marked.parse(String(r.llm_compare)
                    .replace(/\bREVERT\b/gi, 'RETAIN BASELINE')
                    .replace(/\breverted\b/gi, 'baseline-retained')
                    .replace(/\brevert\b/gi, 'retain baseline'))
                : '';
            return `
              <div class="card mb-2">
                <div class="card-header"><strong>Round ${Number(r.round || 0)}</strong> - <code>${escHtml(r.target_agent_id || '')}</code></div>
                <div class="card-body">
                  ${r.candidate_exp_id ? `<p class="mb-1">Candidate: <a href="/exp/${encodeURIComponent(r.candidate_exp_id)}" target="_blank" rel="noopener">${escHtml(r.candidate_exp_id)}</a></p>` : ''}
                  <p class="mb-1"><strong>Effect</strong> P: ${Number(del.precision || 0).toFixed(4)} | R: ${Number(del.recall || 0).toFixed(4)} | F1: ${Number(del.f1 || 0).toFixed(4)}</p>
                  <p class="mb-1"><strong>Status</strong>: ${escHtml(verdict)}${r.reason ? ` (${escHtml(r.reason)})` : ''}</p>
                  <p class="mb-1"><strong>Version</strong>: ${vmText}</p>
                  ${cmp ? `<div class="border-top pt-2 mt-2">${cmp}</div>` : ''}
                </div>
              </div>
            `;
        }).join('')
        : '<p class="text-muted mb-0">No actionable suggestions found.</p>';
    return `
      <div class="card">
        <div class="card-header"><strong>Optimize Loop Result</strong></div>
        <div class="card-body">
          <p class="mb-1">Baseline: <a href="/exp/${encodeURIComponent(base)}" target="_blank" rel="noopener">${escHtml(base)}</a></p>
          <p class="mb-2">Final Best: <a href="/exp/${encodeURIComponent(finalBest)}" target="_blank" rel="noopener">${escHtml(finalBest)}</a></p>
          <p class="mb-2"><strong>Suggestion Count</strong>: ${Number(summary.suggestion_count || 0)}</p>
          <div class="mb-2"><strong>Applied Versions</strong><ul>${versions}</ul></div>
          <div class="border-top pt-2"><strong>Round Effects</strong></div>
          <div class="mt-2">${roundHtml}</div>
        </div>
      </div>
    `;
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