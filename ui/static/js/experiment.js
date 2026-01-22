function renderTestset(data){
    datasetSelect.innerHTML='';
    if (data) {
        data.forEach(f => {
            const selected = f.name === defaultFilename ? 'selected' : '';
            datasetSelect.innerHTML += `<option value="${f.name}" ${selected} data-samples="${f.count}">${f.name} (${f.count} samples)</option>`;
        });

        // 如果有默认文件，显示运行按钮
        if (defaultFilename && datasetSelect.querySelector(`option[value="${defaultFilename}"]`)) {
            $('#runExpBtn').removeClass('d-none').show();  // 显示
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
            datasetSelect.html('<option value="">-- Select a runner first --</option>');
            return;
        }

        $.getJSON(`/testset/api/by_agent/${id}`)
            .done(function(data) {
                renderTestset(data);
                renderTable(datasetSelect.val());
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
        const paneId = $(e.target).attr('href');   // 例如 "#report"
        if(paneId==='#report' && expId && progress===100 ) {
            renderReport(expId);
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
        /* 4. 关闭旧连接 */
    updateProgress(current_process);
    freezeInputAndLink();
    window.agentEventSource?.close();
    /* 6. 新开 SSE */
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
            }else{
                current_status='running';
                current_process=msg.percent;
                updateProgress(current_process);
                updateTableRow(msg.current_index, {"status": msg.status});
            }
        } catch (err) {
           console.error('SSE error:', err);
           window.agentEventSource.close();
           $('#runExpBtn').removeClass('d-none').show();  // 显示
        }

    };
    window.agentEventSource.onerror = err => {
        console.error('SSE error:', err);
        window.agentEventSource.close();
        $('#runExpBtn').removeClass('d-none').show();  // 显示
    };
}



function renderReport(exp_id) {
    $('#reportMarkdown').html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Make report...');
    window.agentEventSource?.close();
    let buffer = '';
    /* 6. 新开 SSE */
    window.agentEventSource = new EventSource(`/stream/report/${exp_id}`);
    window.agentEventSource.onmessage = e => {
        if (e.data === '[DONE]') {
            $('#reportMarkdown').html(marked.parse(buffer));  // 实时解析成 HTML
            window.agentEventSource.close();
            return;
        }
        buffer+=e.data.replace(/\\n/g,'\n');
    };
    window.agentEventSource.onerror = err => {
        console.error('SSE error:', err);
        window.agentEventSource.close();
    };
}