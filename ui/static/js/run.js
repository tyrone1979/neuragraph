function renderTestPanel(id, testSet) {
    const $box = $('#inputFields').empty();
    /* 1. 拿到当前测试集第一行数据  field→value  映射 */
    const realFields =  (id===current) ? graphsById.inputs : agentsData[id].inputs;
    if (testSet && testSetsData[id]?.[testSet]) {
        /*Test set is available.*/
        const fieldValueMap = {};
        const [headers, values] = testSetsData[id][testSet];
        headers.forEach((h, i) => { fieldValueMap[h] = values[i]; });
        realFields.forEach(field => {
                const value = fieldValueMap[field] ?? '';
                $box.append(createField(field, value, realFields.includes(field)));
        });
         // 检查是否有expected字段，如果有则添加
        if (headers.includes('expected')) {
            const expectedValue = fieldValueMap['expected'] ?? '';
            $box.append(createField('expected', expectedValue, false));
        }
    }else{

        realFields.forEach(h => $box.append(createField(h, '', true)));
    }
    $('#resultOutput').empty();
    $('#runAgentPopup').removeClass('hidden');
}

/* 生成单个字段（jQuery 链式写法） */
function createField(header, value, editable) {
    const long = value.length === 0 || value.length > 50;
    const $input = long
        ? $('<textarea>', { rows: 2 })
        : $('<input>', { type: 'text' });

    $input.addClass('form-control').attr({ id: header, name: header }).val(value);

    if (!editable) $input.prop('readonly', true).addClass('readonly-field');

    return $('<div>', { class: 'form-group' })
        .append($('<label>', { for: header, text: header + ': ' }))
        .append($input);
}

/* ========= 事件绑定（jQuery 写法） ========= */
$('#runAgentBtn').on('click', function () {
        const agentId = $('#agentId').val();
        const $testSetSel = $('#testSetSelect').empty();
        $testSetSel.append('<option value="">-- Create New Test data --</option>');
        /* 渲染测试集下拉 */
        if (testSetsData[agentId]) {
            $.each(testSetsData[agentId], function (ts) {
                $testSetSel.append($('<option>', { value: ts, text: ts }));
            });
        }
        renderTestPanel(agentId, $testSetSel.val());
});

/* 切换测试集 */
$('#testSetSelect').on('change', function () {
    if($('#agentId').val()){
        renderTestPanel($('#agentId').val(), $(this).val());
    }else{
        renderTestPanel(currentGraph.id, $(this).val());
    }
});

/* 点击“运行”按钮 */
$('#testWorkflow').on('click', function () {
        const graphId = currentGraph.id;
        const $testSetSel = $('#testSetSelect').empty();
        $testSetSel.append('<option value="">-- Create New Test data --</option>');
        /* 渲染测试集下拉 */
        if (testSetsData[graphId]) {
            $.each(testSetsData[graphId], function (ts) {
                $testSetSel.append($('<option>', { value: ts, text: ts }));
            });
        }

        renderTestPanel(graphId, $testSetSel.val());

});


/* ====== 通用缓存 ====== */
const $runAgentPopup = $('#runAgentPopup');
const $agentPopup = $('#agentPopup');
const $output = $('#resultOutput');
const $diffBody = $('#diffTableBody');

/* ====== 关闭 run-runner 弹窗 ====== */
$(document).on('click', '.run-agent-popup .close-btn', () => {
    $runAgentPopup.addClass('hidden');
    $('#agentId').val('');          // 清空
});

/* ====== 关闭 runner 弹窗 ====== */
$(document).on('click', '.agent-popup .close-btn', () => {
    $agentPopup.addClass('hidden');
    $('#agentId').val('');          // 清空
});

/* ====== 提交运行 ====== */
$('#runAgentSubmit').on('click', () => {
    /* 1. 收集可编辑字段 */
    const formData = {};
    $('#inputFields').find('input, textarea').filter((_, el) => !el.readOnly)
        .each((_, el) => formData[el.name] = el.value);

    /* 2. 原始答案 */
    const originalData = $('#expected').val() || '';

    /* 3. 参数 */
    /* 3. 参数：一行搞定 */
    const params = new URLSearchParams(
        $('#agentId').val()
            ? { agentId: $('#agentId').val(), ...formData }
            : { graphId: currentGraph.id, ...formData }
    );

    /* 4. 关闭旧连接 */
    window.agentEventSource?.close();

    /* 5. 加载态 */
    $output.empty();
    $('#loadingSpinner').removeClass('hidden');

    /* 6. 新开 SSE */
    window.agentEventSource = new EventSource(`/stream/test?${params}`);
    window.agentEventSource.onmessage = e => {
        if (e.data === '[DONE]') {
            window.agentEventSource.close();
            $('#loadingSpinner').addClass('hidden');
            return;
        }
        const clean = e.data
                  .replace(/\\n/g, '')        // 去掉字面量 \n
                  .replace(/\$\$/g, '\n');    // 把 $$ 换成换行
        $output.append(clean);

    };
    window.agentEventSource.onerror = err => {
        console.error('SSE error', err);
        $output.append('\n[Error] SSE connection closed.');
        window.agentEventSource.close();
        $('#loadingSpinner').addClass('hidden');
    };
});
