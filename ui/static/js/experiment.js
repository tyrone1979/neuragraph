function renderRunnerAgentRoster(agents) {
    const $root = $('#runnerAgentRoster');
    if (!$root.length) return;
    const items = Array.isArray(agents) ? agents : [];
    if (!items.length) {
        $root.html('<p class="small text-muted mb-0">Select a workflow to see agent versions.</p>');
        return;
    }
    const rows = items.map((a) => `
      <tr>
        <td>
          <code class="small">${escHtml(a.agent_id || '')}</code>
          <div class="text-muted" style="font-size:.75rem">${escHtml(a.name || '')}${a.graph_id ? ` · <span class="text-monospace">${escHtml(a.graph_id)}</span>` : ''}</div>
        </td>
        <td><code class="small">${escHtml(a.version || 'current')}</code></td>
      </tr>
    `).join('');
    $root.html(`
      <div class="small text-muted mb-1">Workflow agents</div>
      <div class="table-responsive">
        <table class="table table-sm table-bordered mb-0 runner-agent-roster-table">
          <thead><tr><th>Agent</th><th>Version</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
}

function refreshRunnerAgentRoster(runnerIdVal) {
    const id = String(runnerIdVal || '').trim();
    if (!id) {
        renderRunnerAgentRoster([]);
        return;
    }
    $.getJSON(`/exp/api/runner-agents/${encodeURIComponent(id)}`)
        .done((resp) => renderRunnerAgentRoster((resp && resp.agents) || []))
        .fail(() => renderRunnerAgentRoster([]));
}

function renderTestset(data){
    const $datasetSelect = $('#datasetSelect');
    const $tuningSelect = $('#tuningDatasetSelect');
    const $splitSourceSelect = $('#splitSourceSelect');
    const prevTest = $datasetSelect.val() || window._savedTestFilename || defaultFilename;
    const prevTuning = $tuningSelect.val() || window._savedTuningFilename || defaultTuningFilename;
    $datasetSelect.empty();
    $tuningSelect.empty();
    $splitSourceSelect.empty();
    if (data) {
        data.forEach(f => {
            const selected = f.name === prevTest ? 'selected' : '';
            const tuningSelected = f.name === prevTuning ? 'selected' : '';
            $datasetSelect.append(
                `<option value="${f.name}" ${selected} data-samples="${f.count}">${f.name} (${f.count} samples)</option>`
            );
            $tuningSelect.append(
                `<option value="${f.name}" ${tuningSelected}>${f.name} (${f.count} samples)</option>`
            );
            $splitSourceSelect.append(
                `<option value="${f.name}">${f.name} (${f.count} samples)</option>`
            );
        });

        if (prevTest && $datasetSelect.find(`option[value="${CSS.escape(prevTest)}"]`).length) {
            $datasetSelect.val(prevTest);
        }
        if (prevTuning && $tuningSelect.find(`option[value="${CSS.escape(prevTuning)}"]`).length) {
            $tuningSelect.val(prevTuning);
        } else if (!prevTuning && prevTest && $tuningSelect.find(`option[value="${CSS.escape(prevTest)}"]`).length) {
            $tuningSelect.val(prevTest);
        }

        if ($datasetSelect.val()) {
            refreshPreviewIfReady();
        }
    }
}

function previewQueryMatches(runnerId, file, tuning) {
    const current = new URLSearchParams(window.location.search);
    return (
        current.get('runner_id') === runnerId
        && current.get('filename') === file
        && (current.get('tuning_filename') || '') === (tuning || '')
    );
}

function refreshPreviewIfReady(options = {}) {
    const runnerId = $('#runnerId').val();
    const file = $('#datasetSelect').val();
    const tuning = $('#tuningDatasetSelect').val();
    if (!file || !runnerId) {
        return;
    }
    if (!options.force && previewQueryMatches(runnerId, file, tuning)) {
        return;
    }
    renderTable(file, { force: !!options.force });
}

function collectExpFormData() {
    const autoSplitEnabled = $('#autoSplitMode').is(':checked');
    const formData = {
        dataset: $('#datasetSelect').val(),
        test_dataset: $('#datasetSelect').val(),
        tuning_dataset: $('#tuningDatasetSelect').val(),
        runner_type: $('#runnerType').val(),
        runner_id: $('#runnerId').val(),
        runner_display: $('#runnerDisplay').val(),
        samples: $('#datasetSelect').find(':selected').data('samples') || 0,
        exp_id: $('#exp_id').attr('data-id') || $('#exp_id').data('id') || expId,
    };
    if (autoSplitEnabled) {
        formData.split_mode = 'auto';
        formData.split_source_dataset = $('#splitSourceSelect').val();
        formData.split_ratio = Number($('#splitRatioInput').val() || 0.8);
        formData.split_seed = Number($('#splitSeedInput').val() || 42);
    }
    return formData;
}

let _saveConfigTimer = null;
function queueSaveExpConfig() {
    clearTimeout(_saveConfigTimer);
    _saveConfigTimer = setTimeout(saveExpConfigOnly, 500);
}

function saveExpConfigOnly() {
    const formData = collectExpFormData();
    const id = formData.exp_id;
    if (!id || id === 'Not saved yet') return;
    if (!formData.runner_id || !formData.test_dataset) return;
    if (!$('#autoSplitMode').is(':checked') && !formData.tuning_dataset) return;
    $.ajax({
        url: '/exp/api/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success(resp) {
            if (!resp.success) return;
            window._savedTuningFilename = resp.tuning_dataset || formData.tuning_dataset;
            window._savedTestFilename = resp.test_dataset || formData.test_dataset;
            if (resp.tuning_dataset) $('#tuningDatasetSelect').val(resp.tuning_dataset);
            if (resp.test_dataset) $('#datasetSelect').val(resp.test_dataset);
        },
    });
}

function hydrateExpFormFromServer() {
    const id = expId;
    if (!id) return $.Deferred().resolve().promise();
    return $.getJSON(`/exp/api/${encodeURIComponent(id)}`)
        .done((cfg) => {
            if (!cfg || cfg.error) return;
            // Only set dropdown values if they're empty (not already populated by server render).
            // This prevents the async API response from overwriting URL-param-driven selections.
            const currentTest = $('#datasetSelect').val();
            const currentTuning = $('#tuningDatasetSelect').val();
            const apiTest = cfg.test_dataset || '';
            const apiTuning = cfg.tuning_dataset || '';
            if (!currentTest && apiTest) $('#datasetSelect').val(apiTest);
            if (!currentTuning && apiTuning) $('#tuningDatasetSelect').val(apiTuning);
            window._savedTuningFilename = apiTuning || defaultTuningFilename;
            window._savedTestFilename = apiTest || defaultFilename;
            const split = cfg.dataset_split || datasetSplit || {};
            if (split && split.mode === 'auto') {
                $('#autoSplitMode').prop('checked', true);
                $('#autoSplitPanel').show();
                $('#tuningDatasetSelect').prop('disabled', true);
                if (split.source_dataset) $('#splitSourceSelect').val(split.source_dataset);
                if (split.ratio != null) $('#splitRatioInput').val(split.ratio);
                if (split.seed != null) $('#splitSeedInput').val(split.seed);
            }
            if (cfg.progress != null && cfg.progress !== undefined) {
                updateProgress(Number(cfg.progress) || 0);
            }
            const errText = cfg.last_error || '';
            if (errText) {
                $('#error_message').text(errText);
            } else if (String(cfg.status || '').toLowerCase() === 'failed') {
                $('#error_message').text('Batch run failed. Resume or check logs.');
            }
        });
}

function getExpId() {
    return $('#exp_id').attr('data-id') || $('#exp_id').data('id') || expId;
}

const WIZARD_TABS = ['config', 'baseline', 'tuning', 'final'];
const FLOW_TAB_GROUPS = {
    baseline: { container: '#optimizationFlowBaseline', stepIds: ['baseline_test', 'baseline_test_report'] },
    tuning: { container: '#optimizationFlowTuning', stepIds: ['baseline_tuning', 'baseline_tuning_report', 'optimize_rounds'] },
    final: { container: '#optimizationFlowFinal', stepIds: ['final_test', 'final_test_report'] },
};

function showWizardTab(index) {
    const idx = Math.max(0, Math.min(index, WIZARD_TABS.length - 1));
    window._wizardTabIndex = idx;
    window._wizardUserNavigated = true;
    const tabId = WIZARD_TABS[idx];
    $('#expWizardTabs .nav-link').removeClass('active');
    $(`#wizard-tab-btn-${tabId}`).addClass('active');
    $('.wizard-tab-pane').addClass('d-none');
    $(`#wizard-tab-${tabId}`).removeClass('d-none');
    $('#wizardPrevBtn').prop('disabled', idx === 0);
    $('#wizardNextBtn').toggle(idx < WIZARD_TABS.length - 1);
    refreshWizardTabContent(tabId);
}

function refreshWizardTabContent(tabId) {
    if (tabId === 'config') {
        // Refresh datasets when coming back to config tab (no exp_id required)
        const runnerVal = $('#runnerId').val();
        if (runnerVal) {
            $.getJSON('/testset/api/by_agent/' + encodeURIComponent(runnerVal))
                .done(function(resp) {
                    var lite = (resp || []).map(function(t) {
                        return { name: t.name, count: t.count };
                    });
                    renderTestset(lite);
                });
        }
        return;
    }
    const id = getExpId();
    if (!id || id === 'Not saved yet') return;
    if (tabId === 'baseline') {
        loadSavedReportMarkdown(id, '#baselineReportMarkdown', 'report_baseline_test.md');
    }
    if (tabId === 'tuning') {
        updateTuningTabPanels(window._lastFlowSteps, window._lastOptimizationSummary || window._lastPreflightResp);
    }
    if (tabId === 'final') {
        const ctx = window._lastOptimizationSummary;
        if (ctx) {
            renderOptimizationCompare(ctx);
            loadOptimizedReportMarkdown(ctx.optimized_test_exp_id || ctx.final_best_exp_id);
        } else {
            loadSavedReportMarkdown(id, '#optimizedReportMarkdown', 'report_optimized_test.md');
        }
    }
}

function updateWizardTabAccess(flowSteps) {
    const steps = flowSteps || window._lastFlowSteps || DEFAULT_OPT_FLOW;
    const byId = Object.fromEntries(steps.map((s) => [s.id, s]));
    const hasExp = !!(getExpId() && getExpId() !== 'Not saved yet');
    $('#wizard-tab-btn-baseline').prop('disabled', !hasExp);
    const baselineReady = byId.baseline_test_report && byId.baseline_test_report.status === 'done';
    $('#wizard-tab-btn-tuning').prop('disabled', !baselineReady);
    const tuningReady = byId.optimize_rounds && (byId.optimize_rounds.status === 'done' || byId.optimize_rounds.status === 'skipped');
    $('#wizard-tab-btn-final').prop('disabled', !tuningReady);
}

function inferWizardTabFromFlow(steps) {
    const byId = Object.fromEntries((steps || []).map((s) => [s.id, s]));
    if (byId.final_test_report && byId.final_test_report.status === 'done') return 3;
    if (byId.optimize_rounds && (byId.optimize_rounds.status === 'done' || byId.optimize_rounds.status === 'skipped')) return 3;
    if (byId.baseline_test_report && byId.baseline_test_report.status === 'done') return 1;
    // Don't auto-advance just because an experiment is saved.
    // Only advance when actual work has been completed.
    return 0;
}

function initWizardTabFromFlow() {
    if (window._wizardInitialNavDone) return;
    window._wizardInitialNavDone = true;
    if (window._wizardUserNavigated || (window._wizardTabIndex || 0) > 0) return;
    const tabIdx = inferWizardTabFromFlow(window._lastFlowSteps || DEFAULT_OPT_FLOW);
    if (tabIdx > 0) {
        showWizardTab(tabIdx);
    }
}

function _flowDetailText(detail) {
    if (detail == null || detail === '') return '';
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object') {
        if (detail.message) return String(detail.message);
        if (detail.error) return _flowDetailText(detail.error);
        try {
            return JSON.stringify(detail);
        } catch (_e) {
            return String(detail);
        }
    }
    return String(detail);
}

function _asErrorMessage(err) {
    if (!err) return 'Unknown error';
    if (typeof err === 'string') return err;
    if (err.responseJSON && err.responseJSON.error != null) {
        return _flowDetailText(err.responseJSON.error);
    }
    if (err.message) return String(err.message);
    return _flowDetailText(err);
}

function saveConfigForWizard() {
    return new Promise((resolve, reject) => {
        const formData = collectExpFormData();
        const autoSplitEnabled = $('#autoSplitMode').is(':checked');
        if (!formData.runner_id || !formData.test_dataset) {
            reject(new Error('Please select Runner and Test Dataset'));
            return;
        }
        if (!autoSplitEnabled && !formData.tuning_dataset) {
            reject(new Error('Please select Tuning Dataset'));
            return;
        }
        if (autoSplitEnabled && !formData.split_source_dataset) {
            reject(new Error('Please select Auto Split source dataset'));
            return;
        }
        $.ajax({
            url: '/exp/api/save',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success(resp) {
                if (!resp.success) {
                    reject(new Error(resp.error || 'Save failed'));
                    return;
                }
                if (resp.test_dataset) {
                    $('#datasetSelect').val(resp.test_dataset);
                    window._savedTestFilename = resp.test_dataset;
                }
                if (resp.tuning_dataset) {
                    $('#tuningDatasetSelect').val(resp.tuning_dataset);
                    window._savedTuningFilename = resp.tuning_dataset;
                }
                $('#exp_id').text(resp.exp_id);
                $('#exp_id').data('id', resp.exp_id);
                resolve(resp);
            },
            error(xhr) {
                reject(new Error((xhr.responseJSON && xhr.responseJSON.error) || 'Save request failed'));
            },
        });
    });
}

async function runBaselineTabPipeline() {
    const stayTab = window._wizardTabIndex;
    window._suppressAutoReport = true;
    window._wizardLockTab = true;
    setPipelineRunning(true);
    const steps = window._lastFlowSteps || DEFAULT_OPT_FLOW;
    const isRerun = steps.some(
        (s) => (s.id === 'baseline_test' || s.id === 'baseline_test_report') && s.status === 'done'
    );
    if (isRerun) {
        clearDownstreamFlowSteps(0);
        _setLocalFlowStep('baseline_test', 'pending', 'Re-running baseline test...');
        _setLocalFlowStep('baseline_test_report', 'pending', '');
    }
    try {
        await runPipelineStep('baseline_test', { force: isRerun, manageBusy: false });
        await runPipelineStep('baseline_test_report', { force: isRerun, manageBusy: false });
    } finally {
        window._suppressAutoReport = false;
        window._wizardLockTab = false;
        setPipelineRunning(false);
        await refreshOptimizationPreflight();
        if (typeof stayTab === 'number') {
            showWizardTab(stayTab);
        }
    }
}

async function runTuningTabPipeline() {
    setPipelineRunning(true);
    try {
        for (const stepId of ['baseline_tuning', 'baseline_tuning_report', 'optimize_rounds']) {
            await runPipelineStep(stepId, { manageBusy: false });
        }
    } finally {
        setPipelineRunning(false);
        refreshOptimizationPreflight();
    }
}

async function runFinalTabPipeline() {
    setPipelineRunning(true);
    try {
        for (const stepId of ['final_test', 'final_test_report']) {
            await runPipelineStep(stepId, { manageBusy: false });
        }
    } finally {
        setPipelineRunning(false);
        refreshOptimizationPreflight();
    }
}

$(document).ready(function () {
    const runnerId = $('#runnerId');
    const runnerType = $('#runnerType');
    const datasetSelect = $('#datasetSelect');
    const tuningDatasetSelect = $('#tuningDatasetSelect');
    window._savedTuningFilename = defaultTuningFilename;
    window._savedTestFilename = defaultFilename;
    window.onRunnerSelected = function () {
        setTimeout(() => refreshPreviewIfReady(), 500);
    };
    renderTestset(data);
    hydrateExpFormFromServer().always(() => {
        renderTestset(data);
        refreshPreviewIfReady();
        updateProgress(progress || 0);
    });

    const observer = new MutationObserver(function () {
        const id = runnerId.val();
        if (!id) {
            return;
        }

        $.getJSON(`/testset/api/by_agent/${id}`)
            .done(function(resp) {
                const lite = (resp || []).map((t) => ({
                    name: t.name,
                    count: t.count,
                }));
                renderTestset(lite);
                refreshPreviewIfReady();
            })
            .fail(function() {
                datasetSelect.html('<option value="">-- Error loading test sets --</option>');
                tuningDatasetSelect.html('<option value="">-- Error loading test sets --</option>');
            });
        refreshRunnerAgentRoster(id);
    });

    observer.observe(runnerType[0], {attributes: true, childList: true, subtree: true});
    observer.observe(runnerId[0], {attributes: true, childList: true, subtree: true});

    // If runner is already selected (pre-populated from server), load datasets
    // immediately. The MutationObserver only fires on changes, so initial
    // pre-populated values won't trigger it.
    var initialRunnerId = runnerId.val();
    if (initialRunnerId) {
        $.getJSON('/testset/api/by_agent/' + encodeURIComponent(initialRunnerId))
            .done(function(resp) {
                var lite = (resp || []).map(function(t) {
                    return { name: t.name, count: t.count };
                });
                renderTestset(lite);
                refreshPreviewIfReady();
                refreshRunnerAgentRoster(initialRunnerId);
            })
            .fail(function() {
                datasetSelect.html('<option value="">-- Error loading test sets --</option>');
                tuningDatasetSelect.html('<option value="">-- Error loading test sets --</option>');
            });
    }

    $('#autoSplitMode').on('change', function () {
        const enabled = $(this).is(':checked');
        $('#autoSplitPanel').toggle(enabled);
        $('#tuningDatasetSelect').prop('disabled', enabled);
        queueSaveExpConfig();
    });
    $('#tuningDatasetSelect').on('change', queueSaveExpConfig);
    $('#splitSourceSelect, #splitRatioInput, #splitSeedInput').on('change input', queueSaveExpConfig);

    $(document).on('click', '.opt-flow-run-btn', function () {
        const stepId = $(this).data('step-run');
        if (!stepId || $(this).prop('disabled')) return;
        const steps = window._lastFlowSteps || DEFAULT_OPT_FLOW;
        const idx = steps.findIndex((s) => s.id === stepId);
        const isRerun = idx >= 0 && steps[idx].status === 'done';
        if (isRerun) {
            clearDownstreamFlowSteps(idx);
        }
        runPipelineStep(stepId, { force: isRerun });
    });

    $('#runBaselineTabBtn').on('click', function () {
        if (window._pipelineRunning) return;
        runBaselineTabPipeline().catch((err) => alert(err.message || 'Baseline pipeline failed'));
    });
    $('#runTuningTabBtn').on('click', function () {
        if (window._pipelineRunning) return;
        runTuningTabPipeline().catch((err) => alert(err.message || 'Tuning pipeline failed'));
    });
    $('#runFinalTabBtn').on('click', function () {
        if (window._pipelineRunning) return;
        runFinalTabPipeline().catch((err) => alert(err.message || 'Final test pipeline failed'));
    });

    // Batch pause/resume/stop handlers
    $(document).on('click', '#batchPauseBtn', function () {
        const expIdVal = getExpId();
        if (!expIdVal) return;
        $.post(`/stream/pause/${encodeURIComponent(expIdVal)}`)
            .done(function (resp) {
                if (resp.success) {
                    $('#batchPauseBtn').prop('disabled', true).text('Pausing...');
                }
            })
            .fail(function () {
                alert('Failed to pause');
            });
    });

    $(document).on('click', '#batchResumeBtn', function () {
        const expIdVal = getExpId();
        if (!expIdVal) return;
        const progressSelector = '#overallProgress';
        $('#batchResumeBtn').prop('disabled', true).text('Resuming...');
        $.ajax({
            url: '/exp/api/update',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ exp_id: expIdVal, status: 'running' }),
            success: function () {
                stream(expIdVal, { progressSelector });
            },
            error: function () {
                alert('Failed to resume');
                $('#batchResumeBtn').prop('disabled', false).html('<i class="fas fa-play"></i>');
            },
        });
    });

    $(document).on('click', '#batchStopBtn', function () {
        const expIdVal = getExpId();
        if (!expIdVal) return;
        if (!confirm('Stop the current batch run? Completed samples will be saved.')) return;
        $.post(`/stream/stop/${encodeURIComponent(expIdVal)}`)
            .done(function (resp) {
                if (resp.success) {
                    $('#batchStopBtn').prop('disabled', true).text('Stopping...');
                }
            })
            .fail(function () {
                alert('Failed to stop');
            });
    });

    // Tuning batch controls
    $(document).on('click', '#tuningBatchPauseBtn', function () {
        const expIdVal = window._tuningStreamExpId || getExpId();
        if (!expIdVal) return;
        $.post(`/stream/pause/${encodeURIComponent(expIdVal)}`)
            .done(function (resp) {
                if (resp.success) {
                    $('#tuningBatchPauseBtn').prop('disabled', true).text('Pausing...');
                }
            })
            .fail(function () { alert('Failed to pause'); });
    });

    $(document).on('click', '#tuningBatchResumeBtn', function () {
        const expIdVal = window._tuningStreamExpId || getExpId();
        if (!expIdVal) return;
        const progressSelector = '#baselineTuningProgress';
        $('#tuningBatchResumeBtn').prop('disabled', true).text('Resuming...');
        $.ajax({
            url: '/exp/api/update',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ exp_id: expIdVal, status: 'running' }),
            success: function () {
                stream(expIdVal, { progressSelector });
            },
            error: function () {
                alert('Failed to resume');
                $('#tuningBatchResumeBtn').prop('disabled', false).html('<i class="fas fa-play"></i>');
            },
        });
    });

    $(document).on('click', '#tuningBatchStopBtn', function () {
        const expIdVal = window._tuningStreamExpId || getExpId();
        if (!expIdVal) return;
        if (!confirm('Stop the current batch run? Completed samples will be saved.')) return;
        $.post(`/stream/stop/${encodeURIComponent(expIdVal)}`)
            .done(function (resp) {
                if (resp.success) {
                    $('#tuningBatchStopBtn').prop('disabled', true).text('Stopping...');
                }
            })
            .fail(function () { alert('Failed to stop'); });
    });

    $('#wizardPrevBtn').on('click', function () {
        if (window._wizardTabIndex > 0) {
            showWizardTab(window._wizardTabIndex - 1);
        }
    });
    $('#wizardNextBtn').on('click', function () {
        const idx = window._wizardTabIndex || 0;
        if (WIZARD_TABS[idx] === 'config') {
            saveConfigForWizard()
                .then(() => {
                    updateWizardTabAccess(window._lastFlowSteps);
                    showWizardTab(1);
                })
                .catch((err) => alert(err.message || 'Save failed'));
            return;
        }
        if (idx < WIZARD_TABS.length - 1) {
            showWizardTab(idx + 1);
        }
    });
    $('#expWizardTabs .nav-link').on('click', function () {
        if ($(this).prop('disabled')) return;
        const tabId = $(this).data('wizard-tab');
        const tabIndex = WIZARD_TABS.indexOf(tabId);
        if (tabIndex >= 0) {
            showWizardTab(tabIndex);
        }
    });

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
        $('#idx').val('');
        $('#resultOutput').empty();
    });

    window._wizardTabIndex = 0;
    window._wizardUserNavigated = false;
    window._wizardInitialNavDone = false;
    buildAllFlowShells();
    refreshOptimizationPreflight().then(() => {
        initWizardTabFromFlow();
    });
    const initialRunner = $('#runnerId').val() || '';
    if (initialRunner) {
        refreshRunnerAgentRoster(initialRunner);
    } else if (typeof runnerAgentRoster !== 'undefined' && runnerAgentRoster.length) {
        renderRunnerAgentRoster(runnerAgentRoster);
    }
});

function renderTable(file, options = {}) {
    const runnerId = $('#runnerId').val();
    const runnerType = $('#runnerType').val();
    const runnerDisplay = $('#runnerDisplay').val();
    const tuning = $('#tuningDatasetSelect').val();
    if (!file || !runnerId) {
        return;
    }
    if (!options.force && previewQueryMatches(runnerId, file, tuning)) {
        return;
    }
    const params = new URLSearchParams({
        runner_id: runnerId,
        runner_type: runnerType,
        runner_display: runnerDisplay,
        filename: file,
    });
    if (tuning) params.set('tuning_filename', tuning);
    const id = getExpId();
    if (id && id !== 'Not saved yet') {
        window.location.href = `/exp/${encodeURIComponent(id)}?${params.toString()}`;
        return;
    }
    window.location.href = `/exp/new?${params.toString()}`;
}

// 当选择 testset 文件时 → 加载分页数据预览表
$('#datasetSelect').change(function () {
    renderTable($(this).val());
});
/* ====== prevent implicit form submit on Enter ====== */
$('#expForm').submit(function (e) {
    e.preventDefault();
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

function complete_task(exp_id, progress, status, options = {}) {
    const progressSelector = options.progressSelector || '#overallProgress';
    if (status !== 'failed') {
        status = 'completed';
        progress = 100;
    }
    $.ajax({
        url: `/exp/api/update`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ exp_id, status, progress }),
        success: function (resp) {
            if (!resp.success) {
                alert('Save Failed: ' + (resp.error || 'unknown error'));
                return;
            }
            updateProgress(progress, progressSelector);
            if (status === 'completed') {
                if (window._baselineTuningStreamResolve) {
                    const resolve = window._baselineTuningStreamResolve;
                    window._baselineTuningStreamResolve = null;
                    window._baselineTuningStreamReject = null;
                    onBaselineTuningFinished(exp_id);
                    resolve();
                    return;
                }
                if (window._baselineStreamResolve) {
                    const resolve = window._baselineStreamResolve;
                    window._baselineStreamResolve = null;
                    window._baselineStreamReject = null;
                    onBaselineTestFinished(exp_id);
                    resolve();
                    return;
                }
                if (progressSelector === '#baselineTuningProgress') {
                    onBaselineTuningFinished(exp_id);
                } else {
                    onBaselineTestFinished(exp_id);
                }
            } else {
                if (window._baselineTuningStreamReject) {
                    const reject = window._baselineTuningStreamReject;
                    window._baselineTuningStreamResolve = null;
                    window._baselineTuningStreamReject = null;
                    reject(new Error('Tuning baseline failed'));
                    return;
                }
                if (window._baselineStreamReject) {
                    const reject = window._baselineStreamReject;
                    window._baselineStreamResolve = null;
                    window._baselineStreamReject = null;
                    reject(new Error('Baseline test failed'));
                }
                $('#error_message').text('Baseline test failed.');
                unfreezeInputs();
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
function updateProgress(percent, selector) {
    const width = percent;
    const $bar = $(selector || '#overallProgress');
    $bar
        .css('width', width + '%')
        .text(width + '%')
        .toggleClass('progress-bar-animated progress-bar-striped', width < 100);
}

function updateFlowStepProgress(msg, stepId) {
    const p = Math.max(0, Math.min(100, Number(msg.progress || 0)));
    let label = `${p}%`;
    if (msg.sample_index && msg.sample_total) {
        label = `${p}% · ${msg.sample_index}/${msg.sample_total}`;
    } else if (msg.round_index && msg.round_total) {
        label = `${p}% · R${msg.round_index}/${msg.round_total}`;
    }
    const selectorByStep = {
        optimize_rounds: '#optimizationProgress',
        final_test: '#finalTestProgress',
    };
    const $bar = $(selectorByStep[stepId] || '#optimizationProgress');
    $bar.css('width', `${p}%`).text(label);
    const activeStep = msg.flow_step || stepId;
    if (msg.message && activeStep) {
        _setLocalFlowStep(activeStep, 'running', msg.message);
    }
}

function updateOptimizationProgress(msg) {
    updateFlowStepProgress(msg, 'optimize_rounds');
}

function getTuningBaselineExpId(preflightOrSummary) {
    const src = preflightOrSummary || {};
    return (
        src.baseline_tuning_exp_id
        || (src.context && src.context.baseline_tune_exp_id)
        || ''
    );
}

function updateTuningTabPanels(flowSteps, preflightOrSummary) {
    const steps = flowSteps || window._lastFlowSteps || DEFAULT_OPT_FLOW;
    const byId = Object.fromEntries(steps.map((s) => [s.id, s]));
    const tuneReportReady = byId.baseline_tuning_report && byId.baseline_tuning_report.status === 'done';
    const optimizeDone = byId.optimize_rounds && (
        byId.optimize_rounds.status === 'done' || byId.optimize_rounds.status === 'skipped'
    );
    const tuneExpId = getTuningBaselineExpId(preflightOrSummary);

    $('#tuningBaselineReportPanel').toggleClass('d-none', !tuneReportReady);
    if (tuneReportReady && tuneExpId) {
        loadSavedReportMarkdown(tuneExpId, '#tuningBaselineReportMarkdown', 'report_tuning_baseline.md');
    } else if (!tuneReportReady) {
        $('#tuningBaselineReportMarkdown').html('<p class="text-muted p-3">Run tuning baseline report (step 4) to generate.</p>');
    }

    const hasSummary = optimizeDone && !!window._lastOptimizationSummary;
    $('#optimizationSummaryPanel').toggleClass('d-none', !hasSummary);
    if (hasSummary) {
        renderStoredOptimizationSummary(window._lastOptimizationSummary);
    } else if (!optimizeDone) {
        $('#optimizationResult').html('');
    }
}

function renderStoredOptimizationSummary(summary) {
    const payload = summary || window._lastOptimizationSummary;
    if (!payload) {
        return;
    }
    window._lastOptimizationSummary = payload;
    $('#optimizationResult').html(renderOptimizeSummary(payload));
    renderOptimizeSummaryCharts(payload);
}

function freezeInputAndLink() {
    $('#datasetSelect').prop('disabled', true);
    $('#tuningDatasetSelect').prop('disabled', true);
    $('#runnerSearch').prop('disabled', true);
    $('#pageNav').css({ 'pointer-events': 'none', opacity: '0.6' });
}

function unfreezeInputs() {
    $('#datasetSelect').prop('disabled', false);
    $('#tuningDatasetSelect').prop('disabled', false);
    $('#runnerSearch').prop('disabled', false);
    $('#pageNav').css({ 'pointer-events': '', opacity: '' });
}



// Map progress selectors to their batch control button IDs
const _batchControlMap = {
    '#overallProgress': { pause: '#batchPauseBtn', resume: '#batchResumeBtn', stop: '#batchStopBtn' },
    '#baselineTuningProgress': { pause: '#tuningBatchPauseBtn', resume: '#tuningBatchResumeBtn', stop: '#tuningBatchStopBtn' },
};

function _showBatchControls(progressSelector, show) {
    const map = _batchControlMap[progressSelector];
    if (!map) return;
    $(map.pause).toggleClass('d-none', !show);
    $(map.stop).toggleClass('d-none', !show);
    $(map.resume).addClass('d-none');
}

function _showResumeButton(progressSelector, show) {
    const map = _batchControlMap[progressSelector];
    if (!map) return;
    $(map.pause).addClass('d-none');
    $(map.stop).addClass('d-none');
    $(map.resume).toggleClass('d-none', !show);
}

function _hideAllBatchControls(progressSelector) {
    const map = _batchControlMap[progressSelector];
    if (!map) return;
    $(map.pause).addClass('d-none');
    $(map.resume).addClass('d-none');
    $(map.stop).addClass('d-none');
}

function stream(exp_id, options = {}) {
    const progressSelector = options.progressSelector || '#overallProgress';
    let current_process = 0;
    let current_status = 'pending';
    let reconnectCount = 0;
    const maxReconnect = 2;
    let isPaused = false;
    updateProgress(current_process, progressSelector);
    if (progressSelector === '#overallProgress') {
        freezeInputAndLink();
        _setLocalFlowStep('baseline_test', 'running', 'Running baseline test...');
    } else if (progressSelector === '#baselineTuningProgress') {
        _setLocalFlowStep('baseline_tuning', 'running', 'Running tuning baseline...');
    }
    _showBatchControls(progressSelector, true);
    window.agentEventSource?.close();

    function openStream() {
        window.agentEventSource?.close();
        window.agentEventSource = new EventSource(`/stream/run/${exp_id}`);
        window.agentEventSource.onmessage = (e) => {
            if (e.data === '[DONE]') {
                window.agentEventSource.close();
                if (!isPaused) {
                    _hideAllBatchControls(progressSelector);
                    complete_task(exp_id, current_process, current_status, { progressSelector });
                }
                // When paused, the resume button was already shown by the pause handler.
                // When stopped, the controls were already hidden by the stop handler.
                return;
            }
            try {
                const msg = JSON.parse(e.data);
                if (msg.status === 'failed') {
                    $('#error_message').text(msg.error || 'Batch run failed');
                    current_status = 'failed';
                    if (msg.percent != null) {
                        current_process = msg.percent;
                        updateProgress(current_process, progressSelector);
                    }
                    updateTableRow(msg.current_index, { status: 'failed' });
                    _hideAllBatchControls(progressSelector);
                } else if (msg.status === 'paused') {
                    current_status = 'paused';
                    current_process = msg.percent;
                    isPaused = true;
                    updateProgress(current_process, progressSelector);
                    _showResumeButton(progressSelector, true);
                    if (progressSelector === '#overallProgress') {
                        _setLocalFlowStep('baseline_test', 'paused', `Paused at ${msg.completed}/${msg.total}`);
                        updateTableRow(msg.current_index, { status: 'paused' });
                    } else if (progressSelector === '#baselineTuningProgress') {
                        _setLocalFlowStep('baseline_tuning', 'paused', `Paused at ${msg.completed}/${msg.total}`);
                    }
                    unfreezeInputs();
                } else if (msg.status === 'stopped') {
                    current_status = 'stopped';
                    current_process = msg.percent;
                    updateProgress(current_process, progressSelector);
                    _hideAllBatchControls(progressSelector);
                    if (progressSelector === '#overallProgress') {
                        _setLocalFlowStep('baseline_test', 'done', `Stopped at ${msg.completed}/${msg.total}`);
                    }
                    unfreezeInputs();
                } else if (msg.status === 'resumed') {
                    current_process = msg.percent;
                    isPaused = false;
                    updateProgress(current_process, progressSelector);
                    _showBatchControls(progressSelector, true);
                    if (progressSelector === '#overallProgress') {
                        freezeInputAndLink();
                        _setLocalFlowStep('baseline_test', 'running', `Resumed from ${msg.completed}/${msg.total}`);
                    }
                } else {
                    current_status = msg.batch_status || msg.status;
                    current_process = msg.percent;
                    updateProgress(current_process, progressSelector);
                    if (progressSelector === '#overallProgress') {
                        updateTableRow(msg.current_index, { status: msg.status });
                    }
                }
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        };
        window.agentEventSource.onerror = (err) => {
            console.error('SSE error:', err);
            window.agentEventSource.close();
            if (reconnectCount < maxReconnect && !isPaused) {
                reconnectCount += 1;
                $('#error_message').text(`SSE reconnected (${reconnectCount}/${maxReconnect})...`);
                setTimeout(openStream, 1200);
                return;
            }
            if (!isPaused) {
                $('#error_message').text('SSE disconnected. Please retry run.');
                _hideAllBatchControls(progressSelector);
            }
        };
    }

    openStream();
}



function _reportChartScopeKey(rootSel) {
    const $root = $(rootSel || '#reportMarkdown');
    return $root.attr('id') || 'reportMarkdown';
}

function disposeReportCharts(rootSel) {
    const key = _reportChartScopeKey(rootSel);
    const bag = window._reportChartInstances || {};
    const scoped = bag[key];
    if (scoped) {
        Object.values(scoped).forEach((inst) => {
            try {
                inst?.dispose();
            } catch (_err) {
                /* ignore stale echarts instances */
            }
        });
        delete bag[key];
    }
    if (rootSel) {
        $(rootSel).find('.report-inline-chart-card').remove();
    }
    if (!rootSel) {
        if (window.reportOverallChartInstance) {
            window.reportOverallChartInstance.dispose();
            window.reportOverallChartInstance = null;
        }
        window._reportChartInstances = {};
    }
}

const REPORT_CHART_SAMPLE_THRESHOLD = 20;

function stripPerSampleMetricsTables($root, sampleCount) {
    if (Number(sampleCount || 0) <= REPORT_CHART_SAMPLE_THRESHOLD || !$root.length) {
        return;
    }
    const headings = $root.find('h2, h3');
    headings.each(function () {
        const txt = ($(this).text() || '').toLowerCase();
        if (!/metrics/.test(txt)) return;
        let $node = $(this).next();
        while ($node.length && !$node.is('h2, h3')) {
            if ($node.is('table')) {
                const rows = $node.find('tbody tr').length || $node.find('tr').length;
                if (rows > REPORT_CHART_SAMPLE_THRESHOLD + 2) {
                    $node.replaceWith(
                        '<p class="text-muted"><em>Per-sample metrics table omitted (' +
                        sampleCount + ' articles). See charts below.</em></p>'
                    );
                    return false;
                }
            }
            $node = $node.next();
        }
        return true;
    });
}

function renderReportCharts(chartData, rootSel) {
    const root = $(rootSel || '#reportMarkdown');
    const chartScopeKey = _reportChartScopeKey(rootSel);
    if (!chartData || Number(chartData.sample_count || 0) <= 0 || !root.length) {
        disposeReportCharts(rootSel);
        return;
    }
    disposeReportCharts(rootSel);
    const largeRun = Number(chartData.sample_count || 0) > REPORT_CHART_SAMPLE_THRESHOLD
        || chartData.report_mode === 'charts';
    const ensureSlot = (slotName, title, headingRegex) => {
        let $slot = root.find(`[data-report-chart-slot="${slotName}"]`);
        if ($slot.length) {
            $slot.closest('.report-inline-chart-card').find('.small.text-muted').first().text(title);
            return $slot;
        }
        const blockHtml = `
          <div class="report-inline-chart-card" data-report-chart-scope="${chartScopeKey}" data-report-chart-slot-wrap="${slotName}">
            <div class="small text-muted mb-2">${title}</div>
            <div data-report-chart-slot="${slotName}" class="report-inline-chart-canvas"></div>
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
        $slot = root.find(`[data-report-chart-slot="${slotName}"]`);
        return $slot;
    };

    const sampleTitle = largeRun
        ? `Per-sample F1 trend (${chartData.sample_count} articles, chart view)`
        : 'Per-sample F1 Trend';
    const sampleSlot = ensureSlot('sample', sampleTitle, /metrics/);
    const errorSlot = ensureSlot('error', 'FN/FP Composition', /(fn|fp|false negative|false positive)/);
    const impactSlot = ensureSlot('impact', 'Agent Version Impact (F1 Delta)', /(suggestion|agent modification)/);

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
    window._reportChartInstances = window._reportChartInstances || {};
    const scopedInstances = {};
    window._reportChartInstances[chartScopeKey] = scopedInstances;
    scopedInstances.sample = echarts.init(sampleDom);
    scopedInstances.sample.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['F1', 'Precision', 'Recall'] },
        grid: { left: 45, right: 16, top: 30, bottom: 40 },
        dataZoom: largeRun ? [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 4 }] : [],
        xAxis: {
            type: 'category',
            data: xLabels,
            name: 'Sample',
            nameLocation: 'middle',
            nameGap: largeRun ? 36 : 28
        },
        yAxis: { type: 'value', min: 0, max: 1 },
        series: [
            { name: 'F1', type: 'line', smooth: true, data: f1Values },
            { name: 'Precision', type: 'line', smooth: true, data: pValues },
            { name: 'Recall', type: 'line', smooth: true, data: rValues }
        ]
    });

    const err = chartData.error_buckets || {};
    scopedInstances.error = echarts.init(errorDom);
    scopedInstances.error.setOption({
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
    scopedInstances.impact = echarts.init(impactDom);
    scopedInstances.impact.setOption({
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
        Object.values(scopedInstances).forEach((inst) => inst?.resize());
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

function loadAndRenderReportCharts(expIdVal, rootSel) {
    const $root = $(rootSel || '#reportMarkdown');
    return new Promise((resolve) => {
        $.getJSON(`/exp/api/${encodeURIComponent(expIdVal)}/report-charts`)
            .done((payload) => {
                renderReportCharts(payload || {}, rootSel);
                resolve(payload || {});
            })
            .fail(() => {
                disposeReportCharts(rootSel);
                resolve(null);
            });
    });
}

function renderReport(exp_id) {
    /* Legacy: reports are generated inside Optimization flow */
    loadSavedReportMarkdown(exp_id, '#baselineReportMarkdown');
}

function escHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function setOptimizationControlsEnabled(_enabled) {
    updateStepRunButtons(window._lastFlowSteps);
}

function _formatBaselineMetrics(metrics) {
    const m = metrics || {};
    if (m.f1 == null && m.precision == null && m.recall == null) {
        return '';
    }
    return (
        `Baseline test F1=${Number(m.f1 || 0).toFixed(4)}, ` +
        `P=${Number(m.precision || 0).toFixed(4)}, ` +
        `R=${Number(m.recall || 0).toFixed(4)}. ` +
        'Review the baseline report below, then start optimization (steps 3–7).'
    );
}

function showBaselineMetricsSummary(metrics) {
    const text = _formatBaselineMetrics(metrics);
    if (!text) return;
    const steps = (window._lastFlowSteps || DEFAULT_OPT_FLOW).map((s) => ({ ...s }));
    const target = steps.find((s) => s.id === 'baseline_test_report');
    if (target) {
        target.detail = text;
    }
    window._lastFlowSteps = steps;
    renderOptimizationFlow(steps);
}

function showResultAccordion(_wrapId, _expand) {
    /* Results are shown inline in wizard tabs. */
}

function runBaselineTestReportStep(expIdVal, datasets, force) {
    const maxAttempts = 3;
    _setLocalFlowStep('baseline_test_report', 'running', 'Generating baseline test report...');

    function attempt(n) {
        return $.ajax({
            url: `/exp/api/${encodeURIComponent(expIdVal)}/optimization-step/baseline_test_report`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                force: !!force,
                tuning_dataset: datasets.tuning_dataset,
                test_dataset: datasets.test_dataset,
            }),
        }).then((resp) => {
            if (!resp.success) {
                throw new Error(_flowDetailText(resp.error) || 'Baseline report failed');
            }
            if (resp.flow_steps) {
                renderOptimizationFlow(resp.flow_steps);
            } else {
                _setLocalFlowStep('baseline_test_report', 'done', 'Baseline test report ready');
            }
            showBaselineMetricsSummary(resp.baseline_test_metrics || {});
            loadSavedReportMarkdown(expIdVal, '#baselineReportMarkdown', 'report_baseline_test.md');
            return resp;
        }).catch((err) => {
            const msg = _asErrorMessage(err);
            if (n < maxAttempts && /connection|timeout|disconnected/i.test(msg)) {
                _setLocalFlowStep('baseline_test_report', 'running', `Retrying report (${n + 1}/${maxAttempts})...`);
                return new Promise((r) => setTimeout(r, 1500 * n)).then(() => attempt(n + 1));
            }
            _setLocalFlowStep('baseline_test_report', 'failed', msg);
            throw new Error(msg);
        });
    }
    return attempt(1);
}

function generateBaselineTestReport(expIdVal, options = {}) {
    if (!expIdVal) return Promise.reject(new Error('Missing experiment id'));
    return runBaselineTestReportStep(expIdVal, collectExpFormData(), !!options.force);
}

function onBaselineTestFinished(expIdVal) {
    _setLocalFlowStep('baseline_test', 'done', 'Baseline test completed');
    if (window._suppressAutoReport) {
        return;
    }
    generateBaselineTestReport(expIdVal).catch(() => {});
}

function onBaselineTuningFinished(tuneExpId) {
    _setLocalFlowStep('baseline_tuning', 'done', `Completed ${tuneExpId}`);
}

function runBaselineTuningStream(tuneExpId) {
    return new Promise((resolve, reject) => {
        if (!tuneExpId) {
            reject(new Error('Missing tuning baseline experiment id'));
            return;
        }
        window._tuningStreamExpId = tuneExpId;
        $('#baselineTuningProgress')
            .css('width', '0%')
            .text('0%')
            .addClass('progress-bar-animated progress-bar-striped');
        window._baselineTuningStreamResolve = resolve;
        window._baselineTuningStreamReject = reject;
        $.ajax({
            url: '/exp/api/update',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ exp_id: tuneExpId, status: 'running', progress: 0 }),
            success(resp) {
                if (!resp.success) {
                    window._baselineTuningStreamResolve = null;
                    window._baselineTuningStreamReject = null;
                    reject(new Error(resp.error || 'Failed to start tuning baseline stream'));
                    return;
                }
                stream(tuneExpId, { progressSelector: '#baselineTuningProgress' });
            },
            error(xhr) {
                window._baselineTuningStreamResolve = null;
                window._baselineTuningStreamReject = null;
                reject(new Error((xhr.responseJSON && xhr.responseJSON.error) || 'Failed to start tuning baseline stream'));
            },
        });
    });
}

function runBaselineTuningStep(expIdVal, datasets, force) {
    return $.ajax({
        url: `/exp/api/${encodeURIComponent(expIdVal)}/optimization-step/baseline_tuning`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            force: !!force,
            tuning_dataset: datasets.tuning_dataset,
            test_dataset: datasets.test_dataset,
        }),
    }).then((resp) => {
        if (!resp.success) {
            throw new Error(_flowDetailText(resp.error) || 'Tuning baseline prepare failed');
        }
        if (resp.flow_steps) {
            renderOptimizationFlow(resp.flow_steps);
        }
        if (resp.needs_stream && resp.stream_exp_id) {
            _setLocalFlowStep('baseline_tuning', 'running', `Streaming ${resp.stream_exp_id}`);
            return runBaselineTuningStream(resp.stream_exp_id).then(() => $.ajax({
                url: `/exp/api/${encodeURIComponent(expIdVal)}/optimization-step/baseline_tuning`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    force: false,
                    tuning_dataset: datasets.tuning_dataset,
                    test_dataset: datasets.test_dataset,
                }),
            })).then((finalizeResp) => {
                if (!finalizeResp.success) {
                    throw new Error(_flowDetailText(finalizeResp.error) || 'Tuning baseline finalize failed');
                }
                if (finalizeResp.flow_steps) {
                    renderOptimizationFlow(finalizeResp.flow_steps);
                } else {
                    onBaselineTuningFinished(resp.stream_exp_id);
                }
                return finalizeResp;
            });
        }
        if (resp.baseline_tune_exp_id) {
            onBaselineTuningFinished(resp.baseline_tune_exp_id);
        }
        return resp;
    });
}

function _setLocalFlowStep(stepId, status, detail) {
    const steps = (window._lastFlowSteps || DEFAULT_OPT_FLOW).map((s) => ({ ...s }));
    const target = steps.find((s) => s.id === stepId);
    if (target) {
        target.status = status;
        if (detail !== undefined && detail !== null && detail !== '') {
            target.detail = _flowDetailText(detail);
        } else if (status === 'pending') {
            target.detail = '';
        }
    }
    window._lastFlowSteps = steps;
    renderOptimizationFlow(steps);
}

const DEFAULT_OPT_FLOW = [
    { id: 'baseline_test', label: '1. Baseline Test Run', status: 'pending', detail: 'Run on test dataset' },
    { id: 'baseline_test_report', label: '2. Baseline Test Report', status: 'pending', detail: 'Auto-generated after step 1' },
    { id: 'baseline_tuning', label: '3. Tuning Baseline Run', status: 'pending' },
    { id: 'baseline_tuning_report', label: '4. Tuning Report & Refine', status: 'pending' },
    { id: 'optimize_rounds', label: '5. Optimize Rounds (tuning)', status: 'pending' },
    { id: 'final_test', label: '6. Optimized Test Run', status: 'pending' },
    { id: 'final_test_report', label: '7. Compare Test Reports', status: 'pending' },
];

function _flowIcon(status) {
    if (status === 'done') return '✓';
    if (status === 'running') return '…';
    if (status === 'skipped') return '–';
    if (status === 'failed') return '!';
    return '○';
}

const FLOW_STEP_ORDER = [
    'baseline_test',
    'baseline_test_report',
    'baseline_tuning',
    'baseline_tuning_report',
    'optimize_rounds',
    'final_test',
    'final_test_report',
];

const STEP_RUN_LABELS = {
    baseline_test: 'Run',
    baseline_test_report: 'Generate',
    baseline_tuning: 'Run',
    baseline_tuning_report: 'Run',
    optimize_rounds: 'Run',
    final_test: 'Run',
    final_test_report: 'Generate',
};

const ASYNC_PIPELINE_STEPS = new Set([
    'baseline_tuning_report',
    'optimize_rounds',
    'final_test',
    'final_test_report',
]);

function _flowProgressHtml(stepId) {
    if (stepId === 'baseline_test') {
        return `
        <div class="d-flex align-items-center gap-2 w-100">
          <div class="progress exp-progress-step flex-grow-1">
            <div id="overallProgress" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" title="Baseline test progress">0%</div>
          </div>
          <button type="button" class="btn btn-sm btn-warning batch-pause-btn d-none" id="batchPauseBtn" title="Pause"><i class="fas fa-pause"></i></button>
          <button type="button" class="btn btn-sm btn-success batch-resume-btn d-none" id="batchResumeBtn" title="Resume"><i class="fas fa-play"></i></button>
          <button type="button" class="btn btn-sm btn-danger batch-stop-btn d-none" id="batchStopBtn" title="Stop"><i class="fas fa-stop"></i></button>
        </div>`;
    }
    if (stepId === 'baseline_tuning') {
        return `
        <div class="d-flex align-items-center gap-2 w-100">
          <div class="progress exp-progress-step flex-grow-1">
            <div id="baselineTuningProgress" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" title="Tuning baseline progress">0%</div>
          </div>
          <button type="button" class="btn btn-sm btn-warning batch-pause-btn d-none" id="tuningBatchPauseBtn" title="Pause"><i class="fas fa-pause"></i></button>
          <button type="button" class="btn btn-sm btn-success batch-resume-btn d-none" id="tuningBatchResumeBtn" title="Resume"><i class="fas fa-play"></i></button>
          <button type="button" class="btn btn-sm btn-danger batch-stop-btn d-none" id="tuningBatchStopBtn" title="Stop"><i class="fas fa-stop"></i></button>
        </div>`;
    }
    if (stepId === 'optimize_rounds') {
        return `
        <div class="progress exp-progress-step w-100">
          <div id="optimizationProgress" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" title="Optimization progress">0%</div>
        </div>`;
    }
    if (stepId === 'final_test') {
        return `
        <div class="progress exp-progress-step w-100">
          <div id="finalTestProgress" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" title="Optimized test progress">0%</div>
        </div>`;
    }
    return '';
}

function buildFlowShellForContainer(containerSel, stepIds) {
    const $root = $(containerSel);
    if (!$root.length || $root.find('.opt-flow-step').length) {
        return;
    }
    const html = DEFAULT_OPT_FLOW.filter((s) => stepIds.includes(s.id)).map((s) => {
        const row3 = _flowProgressHtml(s.id);
        return `
      <div class="opt-flow-step status-pending" data-step="${escHtml(s.id)}">
        <div class="opt-flow-row opt-flow-row-main">
          <div class="opt-flow-icon">○</div>
          <div class="opt-flow-label">${escHtml(s.label || s.id)}</div>
          <button type="button" class="btn btn-sm btn-outline-primary opt-flow-run-btn ms-auto" data-step-run="${escHtml(s.id)}" disabled>${escHtml(STEP_RUN_LABELS[s.id] || 'Run')}</button>
        </div>
        <div class="opt-flow-row opt-flow-row-status">
          <div class="opt-flow-detail"></div>
        </div>
        <div class="opt-flow-row opt-flow-row-progress${row3 ? '' : ' is-empty'}">
          ${row3}
        </div>
      </div>
    `;
    }).join('');
    $root.html(html);
}

function syncFlowProgressBars(steps) {
    const map = {
        baseline_test: '#overallProgress',
        baseline_tuning: '#baselineTuningProgress',
        optimize_rounds: '#optimizationProgress',
        final_test: '#finalTestProgress',
    };
    (steps || []).forEach((s) => {
        const sel = map[s.id];
        if (!sel) return;
        const $bar = $(sel);
        if (!$bar.length) return;
        if (s.status === 'done' || s.status === 'skipped') {
            updateProgress(100, sel);
        } else if (s.status === 'pending') {
            const label = ($bar.text() || '').trim();
            if (!label || label === '0%') {
                updateProgress(0, sel);
            }
        }
    });
}

function buildAllFlowShells() {
    Object.values(FLOW_TAB_GROUPS).forEach(({ container, stepIds }) => {
        buildFlowShellForContainer(container, stepIds);
    });
}

function buildOptimizationFlowShell() {
    buildAllFlowShells();
}

function clearDownstreamFlowSteps(fromIndex) {
    const steps = (window._lastFlowSteps || DEFAULT_OPT_FLOW).map((s, i) => {
        if (i > fromIndex) {
            const defaults = DEFAULT_OPT_FLOW.find((d) => d.id === s.id) || s;
            return { ...defaults, status: 'pending', detail: defaults.detail || '' };
        }
        return { ...s };
    });
    window._lastFlowSteps = steps;
    renderOptimizationFlow(steps);
}

function updateStepRunButtons(flowSteps) {
    const steps = flowSteps || window._lastFlowSteps || DEFAULT_OPT_FLOW;
    const busy = !!window._pipelineRunning;
    const globalIndex = Object.fromEntries(steps.map((s, i) => [s.id, i]));
    steps.forEach((s, i) => {
        const prevDone = i === 0 || steps[i - 1].status === 'done' || steps[i - 1].status === 'skipped';
        const $btn = $(`.opt-flow-run-btn[data-step-run="${s.id}"]`);
        const canRun = prevDone && !busy && s.status !== 'running';
        $btn.prop('disabled', !canRun);
        if (s.status === 'done' || s.status === 'skipped') {
            $btn.text('Re-run');
        } else {
            $btn.text(STEP_RUN_LABELS[s.id] || 'Run');
        }
    });
    $('#runBaselineTabBtn, #runTuningTabBtn, #runFinalTabBtn').prop('disabled', busy);
    updateWizardTabAccess(steps);
}

function renderOptimizationFlow(flowSteps) {
    const steps = flowSteps && flowSteps.length ? flowSteps : DEFAULT_OPT_FLOW;
    window._lastFlowSteps = steps;
    buildAllFlowShells();
    steps.forEach((s) => {
        $(`.opt-flow-step[data-step="${s.id}"]`).each(function () {
            const $step = $(this);
            $step.attr('class', `opt-flow-step status-${escHtml(s.status || 'pending')}`);
            $step.find('.opt-flow-icon').first().text(_flowIcon(s.status));
            $step.find('.opt-flow-label').first().text(s.label || s.id);
        const $detail = $step.find('.opt-flow-detail').first();
        const detailText = _flowDetailText(s.detail);
        if (detailText) {
            $detail.text(detailText).show();
        } else {
            $detail.text('').hide();
        }
        });
    });
    syncFlowProgressBars(steps);
    updateStepRunButtons(steps);
}

function setPipelineRunning(running) {
    window._pipelineRunning = !!running;
    updateStepRunButtons(window._lastFlowSteps);
}

function runBaselineTestViaSaveAndStream() {
    return new Promise((resolve, reject) => {
        const formData = collectExpFormData();
        const autoSplitEnabled = $('#autoSplitMode').is(':checked');
        if (!formData.runner_id || !formData.test_dataset) {
            reject(new Error('Please select Runner and Test Dataset'));
            return;
        }
        if (!autoSplitEnabled && !formData.tuning_dataset) {
            reject(new Error('Please select Tuning Dataset'));
            return;
        }
        $.ajax({
            url: '/exp/api/save',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success(resp) {
                if (!resp.success) {
                    reject(new Error(resp.error || 'Save failed'));
                    return;
                }
                $('#exp_id').text(resp.exp_id);
                $('#exp_id').data('id', resp.exp_id);
                if (resp.tuning_dataset) {
                    $('#tuningDatasetSelect').val(resp.tuning_dataset);
                    window._savedTuningFilename = resp.tuning_dataset;
                }
                window._baselineStreamResolve = resolve;
                window._baselineStreamReject = reject;
                start_task(resp.exp_id);
            },
            error(xhr) {
                reject(new Error((xhr.responseJSON && xhr.responseJSON.error) || 'Save request failed'));
            },
        });
    });
}

function applyOptimizationSummary(summary) {
    if (!summary) return;
    window._lastOptimizationSummary = summary;
    updateTuningTabPanels(window._lastFlowSteps, summary);
}

function runAsyncOptimizationStep(expIdVal, stepId, datasets, force) {
    return new Promise((resolve, reject) => {
        if (window.optimizationSource) {
            window.optimizationSource.close();
            window.optimizationSource = null;
        }
        _setLocalFlowStep(stepId, 'running', 'Running...');
        const progressBarByStep = {
            optimize_rounds: '#optimizationProgress',
            final_test: '#finalTestProgress',
        };
        const progressSel = progressBarByStep[stepId];
        if (progressSel) {
            $(progressSel)
                .css('width', '0%')
                .text('0%')
                .addClass('progress-bar-animated progress-bar-striped');
        }
        $.ajax({
            url: `/exp/api/${encodeURIComponent(expIdVal)}/optimization-step/${encodeURIComponent(stepId)}/start`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                tuning_dataset: datasets.tuning_dataset,
                test_dataset: datasets.test_dataset,
                force,
            }),
            success(resp) {
                if (!resp.success || !resp.task_id) {
                    const errMsg = _flowDetailText(resp.error) || 'Failed to start';
                    _setLocalFlowStep(stepId, 'failed', errMsg);
                    reject(new Error(errMsg));
                    return;
                }
                const es = new EventSource(`/exp/stream/optimize-loop/${encodeURIComponent(resp.task_id)}`);
                window.optimizationSource = es;
                es.onmessage = function (e) {
                    if (e.data === '[DONE]') {
                        es.close();
                        window.optimizationSource = null;
                        if (progressSel) {
                            $(progressSel).removeClass('progress-bar-animated progress-bar-striped');
                        }
                        resolve();
                        return;
                    }
                    let msg = {};
                    try {
                        msg = JSON.parse(e.data);
                    } catch (_err) {
                        return;
                    }
                    if (stepId === 'optimize_rounds' || stepId === 'final_test') {
                        updateFlowStepProgress(msg, stepId);
                    }
                    if (msg.flow_steps) {
                        renderOptimizationFlow(msg.flow_steps);
                    }
                    if (msg.status === 'failed') {
                        const errMsg = _flowDetailText(msg.error) || 'Step failed';
                        _setLocalFlowStep(stepId, 'failed', errMsg);
                        es.close();
                        window.optimizationSource = null;
                        reject(new Error(errMsg));
                    }
                    const summary = (msg.result && msg.result.summary) || msg.summary;
                    if (summary && (stepId === 'optimize_rounds' || stepId === 'final_test_report')) {
                        applyOptimizationSummary(summary);
                    }
                    if (msg.status === 'completed' && msg.result) {
                        if (msg.result.flow_steps) {
                            renderOptimizationFlow(msg.result.flow_steps);
                        }
                        if (stepId === 'final_test_report' && summary) {
                            renderOptimizationCompare(summary);
                            loadOptimizedReportMarkdown(summary.optimized_test_exp_id);
                        }
                    }
                };
                es.onerror = function () {
                    es.close();
                    window.optimizationSource = null;
                    reject(new Error('Stream disconnected'));
                };
            },
            error(xhr) {
                const msg = _asErrorMessage(xhr);
                _setLocalFlowStep(stepId, 'failed', msg);
                reject(new Error(msg));
            },
        });
    });
}

function runPipelineStep(stepId, options = {}) {
    const force = !!options.force;
    const manageBusy = options.manageBusy !== false;
    const expIdVal = getExpId();
    const datasets = collectExpFormData();
    if (manageBusy) setPipelineRunning(true);
    const done = () => {
        if (manageBusy) {
            setPipelineRunning(false);
            refreshOptimizationPreflight();
        }
    };

    if (stepId === 'baseline_test') {
        const chain = force && expIdVal && expIdVal !== 'Not saved yet'
            ? $.ajax({
                url: `/exp/api/${encodeURIComponent(expIdVal)}/optimization-step/baseline_test`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ force: true, ...datasets }),
            })
            : $.Deferred().resolve();
        return chain
            .then(() => {
                _setLocalFlowStep('baseline_test', 'running', 'Running baseline test...');
                return runBaselineTestViaSaveAndStream();
            })
            .then(done)
            .catch((err) => {
                _setLocalFlowStep('baseline_test', 'failed', err.message || 'Failed');
                if (manageBusy) setPipelineRunning(false);
                alert(err.message || 'Baseline test failed');
            });
    }

    if (stepId === 'baseline_test_report') {
        if (!expIdVal || expIdVal === 'Not saved yet') {
            if (manageBusy) setPipelineRunning(false);
            alert('Save experiment first.');
            return Promise.resolve();
        }
        return runBaselineTestReportStep(expIdVal, datasets, force)
            .then(done)
            .catch((err) => {
                if (manageBusy) setPipelineRunning(false);
                alert(err.message || 'Report generation failed');
            });
    }

    if (stepId === 'baseline_tuning') {
        if (!expIdVal || expIdVal === 'Not saved yet') {
            if (manageBusy) setPipelineRunning(false);
            alert('Save experiment first.');
            return Promise.resolve();
        }
        return runBaselineTuningStep(expIdVal, datasets, force)
            .then(done)
            .catch((err) => {
                _setLocalFlowStep('baseline_tuning', 'failed', err.message || 'Failed');
                if (manageBusy) setPipelineRunning(false);
                alert(err.message || 'Tuning baseline failed');
            });
    }

    if (ASYNC_PIPELINE_STEPS.has(stepId)) {
        if (!expIdVal || expIdVal === 'Not saved yet') {
            if (manageBusy) setPipelineRunning(false);
            alert('Save experiment first.');
            return Promise.resolve();
        }
        return runAsyncOptimizationStep(expIdVal, stepId, datasets, force)
            .then(done)
            .catch((err) => {
                if (manageBusy) setPipelineRunning(false);
                alert(err.message || `Step ${stepId} failed`);
            });
    }

    if (manageBusy) setPipelineRunning(false);
    return Promise.resolve();
}

async function runAllPipeline() {
    if (window._pipelineRunning) return;
    window._suppressAutoReport = true;
    setPipelineRunning(true);
    try {
        for (let i = 0; i < FLOW_STEP_ORDER.length; i += 1) {
            const stepId = FLOW_STEP_ORDER[i];
            const steps = window._lastFlowSteps || DEFAULT_OPT_FLOW;
            const isRerun = steps[i] && steps[i].status === 'done';
            if (isRerun) {
                clearDownstreamFlowSteps(i);
            }
            await runPipelineStep(stepId, { force: isRerun, manageBusy: false });
        }
    } finally {
        window._suppressAutoReport = false;
        setPipelineRunning(false);
        refreshOptimizationPreflight();
    }
}

function refreshOptimizationPreflight() {
    const id = getExpId();
    if (!id || id === 'Not saved yet') {
        renderOptimizationFlow(DEFAULT_OPT_FLOW);
        updateWizardTabAccess(DEFAULT_OPT_FLOW);
        return $.Deferred().resolve().promise();
    }
    const stayTab = window._wizardLockTab ? window._wizardTabIndex : null;
    return $.getJSON(`/exp/api/${encodeURIComponent(id)}/optimization-preflight`)
        .done((resp) => {
            if (!resp.success) {
                renderOptimizationFlow(DEFAULT_OPT_FLOW);
                return;
            }
            if (resp.tuning_dataset) {
                $('#tuningDatasetSelect').val(resp.tuning_dataset);
                window._savedTuningFilename = resp.tuning_dataset;
            }
            if (resp.test_dataset) {
                $('#datasetSelect').val(resp.test_dataset);
                window._savedTestFilename = resp.test_dataset;
            }
            window._lastPreflightResp = resp;
            renderOptimizationFlow(resp.flow_steps || DEFAULT_OPT_FLOW);
            const tabId = WIZARD_TABS[window._wizardTabIndex || 0];
            if (tabId === 'tuning') {
                updateTuningTabPanels(resp.flow_steps, resp);
            } else {
                refreshWizardTabContent(tabId);
            }
            if (resp.baseline_test_ready && !resp.baseline_report_ready && tabId === 'baseline' && !window._suppressAutoReport && !window._pipelineRunning) {
                generateBaselineTestReport(id).then(() => refreshOptimizationPreflight()).catch(() => {});
                return;
            }
            if (resp.awaiting_optimization_confirm) {
                loadSavedReportMarkdown(id, '#baselineReportMarkdown', 'report_baseline_test.md');
                showBaselineMetricsSummary(resp.baseline_test_metrics || {});
            }
            if (resp.optimization_summary) {
                applyOptimizationSummary(resp.optimization_summary);
            }
            if (stayTab != null) {
                showWizardTab(stayTab);
            }
        })
        .fail(() => {
            renderOptimizationFlow(DEFAULT_OPT_FLOW);
        });
}

function loadSavedReportMarkdown(expIdVal, containerSel, reportName) {
    const $el = $(containerSel);
    const filename = reportName || 'report_baseline_test.md';
    if (!expIdVal) {
        $el.html('<p class="text-muted p-3">No report yet.</p>');
        return;
    }
    fetch(`/exp/api/${encodeURIComponent(expIdVal)}/report-file/${encodeURIComponent(filename)}`)
        .then((r) => {
            if (!r.ok && filename !== 'report.md') {
                return fetch(`/exp/api/${encodeURIComponent(expIdVal)}/report-file/report.md`);
            }
            return r;
        })
        .then((r) => {
            if (!r.ok) {
                $el.html('<p class="text-muted p-3">Report not generated yet.</p>');
                return null;
            }
            return r.text();
        })
        .then((text) => {
            if (text === null) return;
            if (!text.trim()) {
                $el.html('<p class="text-muted p-3">Report not generated yet.</p>');
                return;
            }
            $el.html(marked.parse(text));
            enhanceReportMarkupIn($el);
            loadAndRenderReportCharts(expIdVal, containerSel).then((chartData) => {
                if (chartData && Number(chartData.sample_count || 0) > REPORT_CHART_SAMPLE_THRESHOLD) {
                    stripPerSampleMetricsTables($el, chartData.sample_count);
                }
            });
        })
        .catch(() => $el.html('<p class="text-muted p-3">Report not available.</p>'));
}

function showResultAccordion(_wrapId, _expand) {
    /* Results are shown inline in wizard tabs. */
}

function loadOptimizedReportMarkdown(expIdVal) {
    if (!expIdVal) {
        $('#optimizedReportMarkdown').html('<p class="text-muted p-3">No optimized test report yet.</p>');
        return;
    }
    loadSavedReportMarkdown(expIdVal, '#optimizedReportMarkdown', 'report_optimized_test.md');
}

function enhanceReportMarkupIn($root) {
    if (!$root || !$root.length) return;
    styleReportTables($root);
    colorSuggestionPlusMinus($root);
}

function renderOptimizationCompare(summary) {
    if (!summary) {
        $('#optimizationCompare').html('<p class="text-muted p-3">Comparison not available yet.</p>');
        return;
    }
    window._lastOptimizationSummary = summary;
    const b = summary.baseline_test_metrics || {};
    const f = summary.final_test_metrics || summary.final_best_metrics || {};
    const bExp = summary.baseline_exp_id || '';
    const oExp = summary.optimized_test_exp_id || summary.final_best_exp_id || '';
    $('#optimizationCompare').html(`
      <div class="card">
        <div class="card-header"><strong>Test Set Comparison (Baseline vs Optimized)</strong></div>
        <div class="card-body">
          <div class="report-table-wrap">
            <table class="report-table table table-sm mb-0">
              <thead><tr><th>Phase</th><th>Precision</th><th>Recall</th><th>F1</th><th>Experiment</th></tr></thead>
              <tbody>
                <tr>
                  <td>Baseline Test</td>
                  <td>${Number(b.precision || 0).toFixed(4)}</td>
                  <td>${Number(b.recall || 0).toFixed(4)}</td>
                  <td>${Number(b.f1 || 0).toFixed(4)}</td>
                  <td>${bExp ? `<a href="/exp/${encodeURIComponent(bExp)}"><code>${escHtml(bExp)}</code></a>` : '-'}</td>
                </tr>
                <tr>
                  <td>Optimized Test</td>
                  <td>${Number(f.precision || 0).toFixed(4)}</td>
                  <td>${Number(f.recall || 0).toFixed(4)}</td>
                  <td>${Number(f.f1 || 0).toFixed(4)}</td>
                  <td>${oExp ? `<a href="/exp/${encodeURIComponent(oExp)}"><code>${escHtml(oExp)}</code></a>` : '<span class="text-muted">—</span>'}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `);
    loadSavedReportMarkdown(bExp, '#baselineReportMarkdown', 'report_baseline_test.md');
    loadOptimizedReportMarkdown(oExp);
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
    const tuneBaselineExp = summary.baseline_tuning_exp_id || '';
    const finalBest = summary.final_best_exp_id || '';
    const finalGraph = summary.final_graph_id || '';
    const tuningBaselineMetrics = summary.baseline_tuning_metrics || {};
    const finalMetrics = summary.final_best_metrics || {};
    const tuningDataset = summary.tuning_dataset || '';
    const rounds = Array.isArray(summary.rounds) ? summary.rounds : [];
    const verMap = summary.accepted_version_map || {};
    const acceptedCount = rounds.filter((r) => r && r.accepted).length;
    const metricDelta = (key) => {
        const base = Number(tuningBaselineMetrics[key] || 0);
        const fin = Number(finalMetrics[key] || 0);
        return fin - base;
    };
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
              <div class="opt-kpi-label">Tuning Baseline</div>
              <div class="opt-kpi-value">${tuneBaselineExp ? `<a href="/exp/${encodeURIComponent(tuneBaselineExp)}" target="_blank" rel="noopener"><code>${escHtml(tuneBaselineExp)}</code></a>` : '<span class="text-muted">-</span>'}</div>
            </div>
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Optimized Best</div>
              <div class="opt-kpi-value">${finalBest ? `<a href="/exp/${encodeURIComponent(finalBest)}" target="_blank" rel="noopener"><code>${escHtml(finalBest)}</code></a>` : '<span class="text-muted">-</span>'}</div>
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
            <div class="opt-kpi-item">
              <div class="opt-kpi-label">Tuning Dataset</div>
              <div class="opt-kpi-value"><code>${escHtml(tuningDataset || '-')}</code></div>
            </div>
          </div>

          <div class="report-table-wrap mb-3">
            <table class="report-table table table-striped table-hover table-sm align-middle mb-0">
              <thead>
                <tr><th>Metric Context (Tuning)</th><th>Precision</th><th>Recall</th><th>F1</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td>Tuning Baseline</td>
                  <td>${Number(tuningBaselineMetrics.precision || 0).toFixed(4)}</td>
                  <td>${Number(tuningBaselineMetrics.recall || 0).toFixed(4)}</td>
                  <td>${Number(tuningBaselineMetrics.f1 || 0).toFixed(4)}</td>
                </tr>
                <tr>
                  <td>Optimized Best</td>
                  <td>${Number(finalMetrics.precision || 0).toFixed(4)}</td>
                  <td>${Number(finalMetrics.recall || 0).toFixed(4)}</td>
                  <td>${Number(finalMetrics.f1 || 0).toFixed(4)}</td>
                </tr>
                <tr class="table-light">
                  <td>Δ (Optimized − Tuning Baseline)</td>
                  <td>${_fmtDelta(metricDelta('precision'))}</td>
                  <td>${_fmtDelta(metricDelta('recall'))}</td>
                  <td>${_fmtDelta(metricDelta('f1'))}</td>
                </tr>
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
            <p class="small text-muted mb-0 mt-2">Round deltas are measured on the tuning dataset vs the previous round best.</p>
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

function startOptimizationLoop() {
    const expIdVal = $('#exp_id').attr('data-id') || $('#exp_id').data('id') || expId;
    if (!expIdVal || expIdVal === 'Not saved yet') {
        alert('Save experiment and complete baseline test first.');
        return;
    }
    if (window.optimizationSource) {
        window.optimizationSource.close();
        window.optimizationSource = null;
    }
    setOptimizationControlsEnabled(false);
    $('#optimizationStatus').text('Starting optimization...');
    $('#optimizationProgress').css('width', '0%').text('0%').addClass('progress-bar-animated progress-bar-striped');
    $('#optimizationResult').html('');
    $('#optimizationCompare').html('');
    $('#wrapOptimizationResult').addClass('d-none');
    $('#wrapOptimizationCompare').addClass('d-none');
    disposeOptimizeSummaryCharts();

    $.ajax({
        url: '/exp/api/optimize-loop/start',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            exp_id: expIdVal,
            tuning_dataset: $('#tuningDatasetSelect').val(),
            test_dataset: $('#datasetSelect').val(),
        }),
        success: function (resp) {
            if (!resp.success || !resp.task_id) {
                $('#optimizationStatus').text('Failed to start');
                alert(resp.error || 'Optimization failed to start');
                setOptimizationControlsEnabled(true);
                return;
            }
            const taskId = resp.task_id;
            const es = new EventSource(`/exp/stream/optimize-loop/${encodeURIComponent(taskId)}`);
            window.optimizationSource = es;
            es.onmessage = function (e) {
                if (e.data === '[DONE]') {
                    es.close();
                    setOptimizationControlsEnabled(true);
                    $('#optimizationProgress').removeClass('progress-bar-animated progress-bar-striped');
                    refreshOptimizationPreflight();
                    return;
                }
                let msg = {};
                try {
                    msg = JSON.parse(e.data);
                } catch (_err) {
                    return;
                }
                const p = Math.max(0, Math.min(100, Number(msg.progress || 0)));
                updateOptimizationProgress(msg);
                $('#optimizationStatus').text(`${msg.stage || 'running'}: ${msg.message || ''}`);
                if (msg.flow_steps) {
                    renderOptimizationFlow(msg.flow_steps);
                }
                if (msg.status === 'failed') {
                    $('#optimizationStatus').text(`Failed: ${msg.error || 'unknown error'}`);
                    $('#optimizationProgress').removeClass('progress-bar-animated progress-bar-striped');
                    es.close();
                    setOptimizationControlsEnabled(true);
                }
                if (msg.status === 'completed' && msg.summary) {
                    applyOptimizationSummary(msg.summary);
                    renderOptimizationCompare(msg.summary);
                    showResultAccordion('#wrapOptimizationResult', true);
                    if (msg.summary.flow_steps) {
                        renderOptimizationFlow(msg.summary.flow_steps);
                    }
                } else if (msg.summary) {
                    applyOptimizationSummary(msg.summary);
                    showResultAccordion('#wrapOptimizationResult', false);
                }
            };
            es.onerror = function () {
                $('#optimizationStatus').text('Stream disconnected');
                $('#optimizationProgress').removeClass('progress-bar-animated progress-bar-striped');
                es.close();
                setOptimizationControlsEnabled(true);
            };
        },
        error: function (xhr) {
            $('#optimizationStatus').text('Failed to start optimization');
            alert((xhr.responseJSON && xhr.responseJSON.error) || 'Optimization request failed');
            setOptimizationControlsEnabled(true);
        },
    });
}