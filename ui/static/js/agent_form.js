// static/js/agent_form.js
$(document).ready(function () {
    // 表单元素
    const $agentForm = $('#agentForm');
    const $agentId = $('#agentId');
    const $agentName = $('#agentName');
    const $agentType = $('#agentType');
    const $llmFields = $('#llmFields');
    const $pgmFields = $('#pgmFields');
    const $subFields = $('#subFields');
    const $llmUrl = $('#llmUrl');
    const $model = $('#model');
    const $promptDesc = $('#promptDesc');
    const $promptSystem = $('#promptSystem');
    const $promptHuman = $('#promptHuman');
    const program = $('#program');
    const $inputs = $('#inputs');
    const $outputs = $('#outputs');

    const $submitBtn = $('#submitBtn');
    const $toolCheckboxes = $('#toolCheckboxes');
    const $toolsConfig = $('#toolsConfig');
    // 测试面板元素
    const $datasetSelect = $('#datasetSelect');
    const $testInputs = $('#testInputs');
    const $saveDatasetBtn = $('#saveDatasetBtn');
    const $refreshDatasetsBtn = $('#refreshDatasetsBtn');
    const $runTestBtn = $('#runTestBtn');
    const $testResult = $('#testResult');

    // 全局变量
    let currentTestData = null;

    // ==================== 表单类型切换 ====================
// 当前已选工具（从后端传来的 JSON）
    let currentSelectedTools = [];
    let availableLLMs = []; // 全局缓存
    try {
        currentSelectedTools = JSON.parse($toolsConfig.val() || '[]')
            .map(t => typeof t === 'string' ? t : t.name || t);
    } catch (e) {
        console.warn('Invalid tools JSON, reset to empty');
        currentSelectedTools = [];
    }
    function loadAvailableLLMs() {
    $.getJSON('/llms/api/list', function(llms) {
        availableLLMs = llms;
        const $select = $('#llmConfigSelect');
        $select.empty().append('<option value="">-- Select an existing LLM config --</option>');

        llms.forEach(llm => {
            const text = `${llm.id} (${llm.model}) - ${llm.type || 'custom'}`;
            $select.append(`<option value="${llm.id}">${text}</option>`);
        });

        // 编辑模式下自动选中当前 runner 使用的 LLM 配置
        if (isEdit && agentData && agentData.model) {
            $select.val(agentData.model);
        }
    }).fail(() => {
        alert('Failed to load LLM configurations');
    });
}

// 下拉变更时，只更新隐藏字段
$('#llmConfigSelect').on('change', function() {
    const selectedId = $(this).val();
    $('#llmConfigId').val(selectedId || '');
});
    // ==================== JSON 字段处理 ====================
// 切换 Type 时显示对应区域
    function updateFieldsVisibility() {
        const type = $agentType.val();
        $llmFields.hide();
        $pgmFields.hide();
        $subFields.hide();

        if (type === 'LLM') $llmFields.show();
        else if (type === 'PGM') $pgmFields.show();
        else if (type === 'SUB') $subFields.show();

    }

    $agentType.on('change', function () {
            if ($(this).val() === 'LLM') {
                loadAvailableTools();
                loadAvailableLLMs();
            }

            updateFieldsVisibility();
    });

    updateFieldsVisibility(); // 初始
    // 解析 JSON 字段
    function parseJSONField(value, defaultValue = null) {
        if (!value || value.trim() === '') {
            return defaultValue;
        }
        try {
            return JSON.parse(value);
        } catch (e) {
            console.error('JSON parse error:', e);
            throw new Error(`Invalid JSON format: ${e.message}`);
        }
    }

    // 加载可用工具列表（从 /tools/api/list 或直接从全局变量）
    function loadAvailableTools() {
        $.getJSON('/tools/api/list', function (tools) {
            $toolCheckboxes.empty();

            if (tools.length === 0) {
                $toolCheckboxes.append('<div class="text-center text-muted py-4">No tools available</div>');
                return;
            }

            tools.forEach(tool => {
                const toolId = tool.id;
                const checked = currentSelectedTools.includes(toolId);

                const $label = $('<label class="form-check d-block mb-2"></label>');
                const $input = $(`<input type="checkbox" class="form-check-input me-2" value="${toolId}">`)
                    .prop('checked', checked);

                $label.append($input);
                $label.append(`<strong>${tool.name}</strong>`);
                if (tool.description) {
                    $label.append(`<small class="text-muted d-block ms-4">${tool.description}</small>`);
                }

                $toolCheckboxes.append($label);
            });

            // 绑定事件：复选框变化 → 更新 JSON
            $toolCheckboxes.find('input[type=checkbox]').on('change', syncToolsToJson);
        }).fail(function () {
            $toolCheckboxes.html('<div class="text-danger">Failed to load tools</div>');
        });
    }

    // 同步复选框状态到 JSON 文本框
    function syncToolsToJson() {
        const selected = [];
        $toolCheckboxes.find('input[type=checkbox]:checked').each(function () {
            selected.push($(this).val());
        });

        // 简单格式：["tool1", "tool2"]
        $toolsConfig.val(JSON.stringify(selected, null, 2));
    }

    // JSON 文本框手动编辑后 → 更新复选框（可选，防冲突可不实现，这里简单实现）
    $toolsConfig.on('input', function () {
        try {
            const parsed = JSON.parse($(this).val() || '[]');
            const normalized = parsed.map(t => typeof t === 'string' ? t : t.name || t);

            $toolCheckboxes.find('input[type=checkbox]').each(function () {
                const val = $(this).val();
                $(this).prop('checked', normalized.includes(val));
            });
        } catch (e) {
            // JSON 非法时不处理
        }
    });


    // 逗号分隔字符串转数组，失败返回空数组
    function parseCommaList(str) {
      return str
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
    }
    function parseOutputs() {
      return {
        name: $('#outputName').val().trim(),
        type: $('#outputType').val()
      };
    }

    // ==================== 表单数据收集 ====================

    // 收集表单数据
    function collectFormData() {
        const formData = {
            id: $agentId.val().trim(),
            name: $agentName.val().trim(),
            type: $agentType.val()
        };

        // 处理 JSON 字段
        try {
            formData.inputs = parseCommaList($inputs.val());
            formData.outputs = parseOutputs();
        } catch (e) {
            throw e;
        }

        // LLM 相关字段
        if (formData.type === 'LLM') {
            const model =  $('#llmConfigId').val().trim();
            if (model) formData.model = model;

            const promptDesc = $promptDesc.val().trim();
            const promptSystem = $promptSystem.val().trim();
            const promptHuman = $promptHuman.val().trim();

            if (promptDesc || promptSystem || promptHuman) {
                formData.prompt_template = {
                    description: promptDesc,
                    system: promptSystem,
                    human: promptHuman
                };
            }

            // ========== 新增：收集 Tools 配置 ==========
            const toolsConfigText = $toolsConfig.val().trim();

            if (toolsConfigText) {
                try {
                    const tools = JSON.parse(toolsConfigText);

                    // 简单验证：必须是数组，且元素是字符串或对象（带 name/module）
                    if (Array.isArray(tools)) {
                        // 如果是纯字符串数组，直接用
                        // 如果是对象数组，取 name 字段（兼容不同格式）
                        const normalizedTools = tools.map(t => {
                            if (typeof t === 'string') return t;
                            if (typeof t === 'object' && t !== null && t.name) return t.name;
                            throw new Error(`Invalid tool entry: ${JSON.stringify(t)}`);
                        });

                        formData.tools = normalizedTools;
                    } else {
                        throw new Error('Tools must be a JSON array');
                    }
                } catch (e) {
                    // 这里你可以根据需要抛错、alert，或者静默忽略
                    console.error('Tools JSON 解析失败:', e);
                    alert('Tools Configuration JSON 格式错误，请检查！\n' + e.message);
                    throw e; // 阻止提交
                }
            } else {
                // 没填 tools 时清空（可选）
                formData.tools = [];
            }

        }

        if (formData.type==='PGM'){
            const program = $('#program').val();
            if (program) formData.process = program;
        }
        if (formData.type==='SUB'){
            const idx= $('#indexForLoop').val();
            if (idx) formData.idx=idx;
        }
        return formData;
    }

    // ==================== 表单验证 ====================

    // 验证表单数据
    function validateFormData(data) {
        // 验证 Agent ID
        if (!data.id) {
            alert('Agent ID is required');
            $agentId.focus();
            return false;
        }

        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(data.id)) {
            alert('Agent ID must be a valid Python identifier (letters, digits, underscore, starting with letter or underscore)');
            $agentId.focus();
            return false;
        }

        // 验证 Agent Name
        if (!data.name) {
            alert('Agent Name is required');
            $agentName.focus();
            return false;
        }

        // 验证 Agent Type
        if (!data.type) {
            alert('Agent Type is required');
            $agentType.focus();
            return false;
        }



        if (data.type==='PGM' && !data.process){
            alert('Invalid Program code.')
            return false;
        }
        if (data.type==='SUB' && !data.idx){
            alert('Index for Loop MUST be provided.');
            return false;
        }

        return true;
    }

    // ==================== 保存/更新 Agent ====================

    $agentForm.on('submit', function (e) {
        e.preventDefault();

        try {
            const formData = collectFormData();

            if (!validateFormData(formData)) {
                return;
            }

            // 禁用提交按钮防止重复提交
            const originalText = $submitBtn.html();
            $submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');

            const method =  'PUT';
            const url = `/agents/api/${formData.id}` ;

            $.ajax({
                url: url,
                type: method,
                contentType: 'application/json',
                data: JSON.stringify(formData),
                success: function (response) {
                    alert(isEdit ? 'Agent updated successfully!' : 'Agent created successfully!');
                    $submitBtn.prop('disabled', false).html('Update');

                },
                error: function (xhr) {
                    $submitBtn.prop('disabled', false).html(originalText);
                    const errorMsg = xhr.responseJSON?.error || 'Unknown error';
                    alert(`Save failed: ${errorMsg}`);
                }
            });
        } catch (error) {
            alert(`Form error: ${error.message}`);
        }
    });

    // ==================== 测试数据集功能 ====================

    // 初始化测试数据集下拉框
    function initTestDatasets() {
        const agentId = $agentId.val();
        if (!agentId) {
            $datasetSelect.empty();
            $datasetSelect.append('<option value="">-- No Agent ID --</option>');
            $datasetSelect.prop('disabled', true);
            return;
        }

        $datasetSelect.prop('disabled', false);

        // 显示加载状态
        const originalHtml = $datasetSelect.html();
        $datasetSelect.html('<option value="">Loading test datasets...</option>');

        $.get(`/testset/api/by_agent/${agentId}`, function (tests) {
            $datasetSelect.empty();
            $datasetSelect.append('<option value="">-- Create New Test data --</option>');

            if (tests && Array.isArray(tests)) {
                tests.forEach(test => {
                    $datasetSelect.append(
                        `<option value="${test.id}" data-agent="${test.agent_id}">
                            ${test.name || test.id}
                        </option>`
                    );
                });

                if (tests.length > 0) {
                    // 自动选择第一个测试数据集
                    $datasetSelect.val(tests[0].id).trigger('change');
                }
            } else {
                $datasetSelect.append('<option value="">No test datasets found</option>');
            }
        }).fail(function (xhr) {
            console.error('Failed to load test datasets:', xhr);
            $datasetSelect.empty();
            $datasetSelect.append('<option value="">Error loading datasets</option>');
        });
    }

    // 刷新测试数据集
    $refreshDatasetsBtn.on('click', function () {
        $(this).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>');
        initTestDatasets();
        // 清空测试输入区域
        clearTestInputs();
        setTimeout(() => {
            $(this).html('<i class="fas fa-sync"></i> Refresh');
        }, 500);
    });

    // 测试数据集选择变化
    $datasetSelect.on('change', function () {
        const option = $(this).find('option:selected');
        const testId = option.val();
        const agentId = option.data('runner') || $agentId.val();

        currentTestData = null;

        if (!testId || !agentId) {
            // 选择"Create New Test data"，清空输入区域
            clearTestInputs();
            $saveDatasetBtn.prop('disabled', false);
            $runTestBtn.prop('disabled', true);
            $testResult.text('');
            return;
        }

        // 显示加载状态
        $testInputs.html('<div class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Loading test data...</div>');

        // 加载选中的测试数据集
        $.get(`/testset/api/${agentId}/${testId}`, function (testData) {
            currentTestData = testData;
            // 根据inputs字段生成输入表单
            renderTestInputs(testData);
            $saveDatasetBtn.prop('disabled', true); // 已有数据集不能覆盖保存
            $runTestBtn.prop('disabled', false);
            $testResult.text('');
        }).fail(function (xhr) {
            $testInputs.html('<div class="alert alert-danger">Failed to load test data</div>');
            alert('Failed to load test data: ' + (xhr.responseJSON?.error || 'Unknown error'));
        });
    });

    // 定义需要显示为 textarea 的字段类型
    const TEXTAREA_FIELDS = ['text', 'abstract','synonyms',
        'tree', 'heads','tails','entities', 'predicted_entities',
        'triples' ,'sentence',"expected_entities"];
    // 清空测试输入
    function clearTestInputs() {
        $testInputs.empty();

        // 根据当前agent的inputs字段创建空输入框
        try {
            const inputs = parseJSONField($inputs.val(), []);
            if (inputs && Array.isArray(inputs) && inputs.length > 0) {
                inputs.forEach((input, index) => {
                    const inputName = input || `input_${index + 1}`;
                    const inputType = 'text';
                    const inputDesc = '';

                    // 检查是否需要 textarea
                    const isTextarea = TEXTAREA_FIELDS.some(field =>
                        inputName.toLowerCase() === field.toLowerCase()
                    );
                    let inputHtml;

                    if (isTextarea) {
                        // 创建 textarea 输入框
                        inputHtml = `
                        <div class="mb-3">
                            <label class="form-label small fw-medium">
                                ${inputName}
                                ${inputDesc ? `<span class="text-muted"> - ${inputDesc}</span>` : ''}
                                <span class="badge bg-info ms-1">Text Area</span>
                            </label>
                            <textarea class="form-control form-control-sm"
                                      name="${inputName}"
                                      placeholder="${inputType}"
                                      data-type="${inputType}"
                                      rows="4"></textarea>
                        </div>
                    `;
                    } else {
                        // 创建普通 input 输入框
                        inputHtml = `
                        <div class="mb-3">
                            <label class="form-label small fw-medium">
                                ${inputName}
                                ${inputDesc ? `<span class="text-muted"> - ${inputDesc}</span>` : ''}
                            </label>
                            <input type="text" class="form-control form-control-sm"
                                   name="${inputName}"
                                   value=""
                                   placeholder="${inputType}"
                                   data-type="${inputType}">
                        </div>
                    `;
                    }

                    $testInputs.append(inputHtml);
                });
            } else {
                $testInputs.html('<div class="alert alert-info">No input fields defined in runner configuration</div>');
            }
        } catch (e) {
            $testInputs.html('<div class="alert alert-warning">Invalid inputs format in runner configuration</div>');
        }
    }

    // 渲染测试输入表单
    function renderTestInputs(testData) {
        $testInputs.empty();

        if (testData.inputs && Object.keys(testData.inputs).length > 0) {
            // 获取agent的inputs定义用于显示类型信息
            let agentInputs = [];
            try {
                agentInputs = parseJSONField($inputs.val(), []);
            } catch (e) {
                // 忽略错误，使用默认
            }

            // 创建输入映射，方便查找类型信息
            const inputMap = {};
            agentInputs.forEach(input => {
                if (input.name) {
                    inputMap[input.name] = input;
                }
            });

            // 渲染每个输入字段
            Object.entries(testData.inputs).forEach(([name, value]) => {
                const inputInfo = inputMap[name] || {};
                const inputType = inputInfo.type || 'text';
                const inputDesc = inputInfo.description || '';

                // 检查是否需要 textarea
                const isTextarea = TEXTAREA_FIELDS.some(field =>

                    name.toLowerCase() === field.toLowerCase()

                );

                let inputHtml;

                if (isTextarea) {
                    // 创建 textarea 输入框
                    const rows = Math.min(Math.max(3, Math.ceil((value || '').length / 50)), 10); // 动态计算行数
                    inputHtml = `
                    <div class="mb-3">
                        <label class="form-label small fw-medium">
                            ${name}
                            ${inputDesc ? `<span class="text-muted"> - ${inputDesc}</span>` : ''}
                            <span class="badge bg-info ms-1">Text Area</span>
                        </label>
                        <textarea class="form-control form-control-sm"
                                  name="${name}"
                                  placeholder="${inputType}"
                                  data-type="${inputType}"
                                  rows="${rows}">${value || ''}</textarea>
                    </div>
                `;
                } else {
                    // 创建普通 input 输入框
                    inputHtml = `
                    <div class="mb-3">
                        <label class="form-label small fw-medium">
                            ${name}
                            ${inputDesc ? `<span class="text-muted"> - ${inputDesc}</span>` : ''}
                        </label>
                        <input type="text" class="form-control form-control-sm"
                               name="${name}"
                               value="${value || ''}"
                               placeholder="${inputType}"
                               data-type="${inputType}">
                    </div>
                `;
                }

                $testInputs.append(inputHtml);
            });
        } else {
            $testInputs.html('<div class="alert alert-info">No input data in this test dataset</div>');
        }
    }

    // 收集测试输入（需要更新以处理 textarea）
    function collectTestInputs() {
        const inputs = {};

        // 收集 input 元素
        $testInputs.find('input[type="text"]').each(function () {
            const $input = $(this);
            const name = $input.attr('name');
            const value = $input.val();
            const type = $input.data('type') || 'text';

            if (name) {
                inputs[name] = {
                    value: value,
                    type: type
                };
            }
        });

        // 收集 textarea 元素
        $testInputs.find('textarea').each(function () {
            const $textarea = $(this);
            const name = $textarea.attr('name');
            const value = $textarea.val();
            const type = $textarea.data('type') || 'text';

            if (name) {
                inputs[name] = {
                    value: value,
                    type: type,
                    isTextarea: true
                };
            }
        });

        return inputs;
    }

    // 保存为测试数据集
    $saveDatasetBtn.on('click', function () {
        const inputs = collectTestInputs();
        const agentId = $agentId.val();

        if (!agentId) {
            alert('Agent ID is required to save test dataset');
            return;
        }

        if (Object.keys(inputs).length === 0) {
            alert('No input data to save');
            return;
        }

        // 简化inputs结构，只保存值
        const simpleInputs = {};
        Object.entries(inputs).forEach(([name, data]) => {
            simpleInputs[name] = data.value;
        });

        const datasetName = prompt('Enter test dataset name:', `test_${new Date().toISOString().slice(0, 10)}`);

        if (!datasetName || datasetName.trim() === '') return;

        const testData = {
            name: datasetName.trim(),
            agent_id: agentId,
            inputs: simpleInputs
        };

        // 显示保存中状态
        const originalText = $saveDatasetBtn.html();
        $saveDatasetBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');

        $.ajax({
            url: '/testset/api',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(testData),
            success: function (response) {
                alert('Test dataset saved successfully!');
                // 刷新下拉框
                initTestDatasets();
                // 选择新创建的测试数据集
                setTimeout(() => {
                    $datasetSelect.val(response.id).trigger('change');
                }, 500);
            },
            error: function (xhr) {
                alert('Save failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            },
            complete: function () {
                $saveDatasetBtn.prop('disabled', false).html(originalText);
            }
        });
    });

    // 保存 Agent 的函数
    function saveAgentBeforeTest(agentId, inputs) {
        try {
            const formData = collectFormData();

            if (!validateFormData(formData)) {
                alert('Cannot save runner: Invalid form data');
                return;
            }

            // 禁用运行测试按钮
            $runTestBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');

            const method =  'PUT' ;
            const url =`/agents/api/${formData.id}`;

            $.ajax({
                url: url,
                type: method,
                contentType: 'application/json',
                data: JSON.stringify(formData),
                success: function (response) {

                    // Agent 保存成功后，开始流式测试
                    startStreamingTest(agentId, inputs, formData);
                },
                error: function (xhr) {
                    $runTestBtn.prop('disabled', false).html('<i class="fas fa-play me-1"></i> Run Test');
                    const errorMsg = xhr.responseJSON?.error || 'Unknown error';
                    alert(`Save agent failed: ${errorMsg}. Cannot run test.`);
                }
            });
        } catch (error) {
            $runTestBtn.prop('disabled', false).html('<i class="fas fa-play me-1"></i> Run Test');
            alert(`Form error: ${error.message}`);
        }
    }

    // 修改 runTestBtn 的点击事件处理
    $runTestBtn.on('click', function () {
        const agentId = $agentId.val();

        if (!agentId) {
            alert('Agent ID is required to run test');
            return;
        }

        // 收集测试输入
        const testInputs = collectTestInputs();

        if (Object.keys(testInputs).length === 0) {
            alert('No input data to test');
            return;
        }

        // 1. 先保存 Agent（使用 Agent 的所有属性）
        saveAgentBeforeTest(agentId, testInputs);
    });

    // ==================== 表单初始化 ====================


    // 监听Agent ID变化，更新测试数据集
    $agentId.on('input', function () {
        initTestDatasets();
    });


    // 开始流式测试的函数
    function startStreamingTest(agentId, testInputs, agentData) {
        // 2. 更新运行按钮状态
        $runTestBtn.html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...');

        // 3. 准备参数
        // 将 testInputs 转换为简单对象（只保留值）
        const simpleInputs = {};
        Object.entries(testInputs).forEach(([name, data]) => {
            simpleInputs[name] = data.value;
        });

        // 创建 URL 参数
        const params = new URLSearchParams({
            agentId: agentId,
            ...simpleInputs
        });

        // 4. 清空测试结果并显示加载状态
        $testResult.empty();

        // 5. 关闭旧的 EventSource 连接
        if (window.agentEventSource) {
            window.agentEventSource.close();

        }

        // 6. 创建新的 EventSource 连接
        const streamUrl = `/stream/test?${params}`;

        window.agentEventSource = new EventSource(streamUrl);

        // 处理接收到的消息
        window.agentEventSource.onmessage = function (e) {

            if (e.data === '[DONE]') {
                // 测试完成
                window.agentEventSource.close();
                $('#loadingSpinner').addClass('d-none');
                $runTestBtn.prop('disabled', false).html('<i class="fas fa-play me-1"></i> Run Test');

                // 隐藏停止按钮（如果存在）
                if ($('#stopTestBtn').length) {
                    $('#stopTestBtn').hide();
                }

                return;
            }
            $testResult.append(e.data.replace(/\\n/g, ''));
            // 自动滚动到底部
            $testResult.scrollTop($testResult[0].scrollHeight);
        };

        // 处理错误
        window.agentEventSource.onerror = function (err) {
            console.error('SSE error:', err);

            // 显示错误信息
            $testResult.append('\n\n[Error] SSE connection closed or error occurred.\n');

            // 隐藏加载指示器
            $('#loadingSpinner').addClass('d-none');

            // 恢复按钮状态
            $runTestBtn.prop('disabled', false).html('<i class="fas fa-play me-1"></i> Run Test');

            // 隐藏停止按钮（如果存在）
            if ($('#stopTestBtn').length) {
                $('#stopTestBtn').hide();
            }

            // 关闭连接
            if (window.agentEventSource) {
                window.agentEventSource.close();
                window.agentEventSource = null;
            }
        };

    }

    // 在页面卸载时关闭 EventSource 连接
    $(window).on('beforeunload', function () {
        if (window.agentEventSource) {
            window.agentEventSource.close();
        }
    });


// 绑定工具相关事件
function bindToolEvents() {
    // 全选/取消全选
    $('#selectAllTools').on('change', function() {
        $('.tool-checkbox').prop('checked', $(this).prop('checked'));
        updateToolsConfigFromCheckboxes();
    });

    // 单个复选框变化
    $('.tool-checkbox').on('change', function() {
        updateToolsConfigFromCheckboxes();
    });

    // 更新配置按钮
    $('#updateToolsConfig').on('click', function() {
        updateToolsConfigFromCheckboxes();
    });
}

// 根据复选框更新工具配置
function updateToolsConfigFromCheckboxes() {
    const selectedTools = [];

    $('.tool-checkbox:checked').each(function() {
        const toolData = $(this).data('tool');
        selectedTools.push({
            name: toolData.name,
            module: toolData.module,
            function: toolData.function,
            id: toolData.id
        });
    });

    // 更新配置文本框
    $('#toolsConfig').val(JSON.stringify(selectedTools, null, 2));
}

    // 页面加载初始化
    function init() {
        // 初始化测试数据集
        initTestDatasets();
        // 清空测试输入区域
        clearTestInputs();
        if ($agentType.val() === 'LLM') {
                loadAvailableTools();
                loadAvailableLLMs();
            }
        // 如果有初始测试数据集且是编辑模式，加载第一个
        if (isEdit && testSets && testSets.length > 0) {
            // 在编辑模式下，等待一小段时间让下拉框加载完成
            setTimeout(() => {
                if ($datasetSelect.find('option').length > 1) {
                    $datasetSelect.val(testSets[0].id).trigger('change');
                }
            }, 500);
        }
    }

    // 执行初始化
    init();
});