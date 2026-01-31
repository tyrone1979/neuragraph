// static/js/runner.js
$(document).ready(function () {
    const $grid = $('#agentGrid');
    const $noResults = $('#noResults');
    const $searchInput = $('#searchInput');

    // 获取 badge 样式
    function getTypeBadge(type) {
        if (type === 'LLM') return 'bg-primary';
        if (type === 'PGM') return 'bg-info';
        return 'bg-secondary';
    }

    // 创建单个 agent 卡片
    function createAgentCard(agent) {
        let typeText = agent.type || 'Unknown';
        let typeBadge = getTypeBadge(agent.type);
        let title = agent.name || agent.id || 'Unnamed Agent';

        let modelHtml = agent.model
            ? `<p class="card-text"><strong>Model:</strong> ${agent.model}</p>`
            : '';

        return `
        <div class="col">
            <div class="card h-100 shadow-sm">
                <div class="card-body">
                    <h5 class="card-title">${title}</h5>
                    <p class="card-text">
                        <strong>ID:</strong> <code>${agent.id}</code><br>
                        <strong>Type:</strong>
                        <span class="badge ${typeBadge}">${typeText}</span>
                    </p>
                    ${modelHtml}
                </div>
                <div class="card-footer bg-transparent d-flex justify-content-between">
                    <a href="/agents/${agent.id}/edit" class="btn btn-sm btn-outline-primary">Edit</a>
                    <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${agent.id}" data-name="${title}">Delete</button>
                </div>
            </div>
        </div>`;
    }

    // 创建分组标题（占满整行）
    function createGroupHeader(type, count) {
        let typeBadge = getTypeBadge(type);
        let displayType = type || 'Unknown';
        return `
        <div class="col-12">
            <h4 class="border-bottom pb-2 mb-3">
                <span class="badge ${typeBadge} me-2">${displayType}</span>
                <small class="text-muted">(${count})</small>
            </h4>
        </div>`;
    }

    // 加载 Agent 列表
    function loadAgents(query = '') {
        let url = '/agents/api/list';
        if (query) {
            url += '?q=' + encodeURIComponent(query);
        }

        $.get(url, function (agents) {
            $grid.empty();

            if (agents.length === 0) {
                $noResults.removeClass('d-none');
                return;
            }
            $noResults.addClass('d-none');

            // 1. 按 type 分组
            let groups = {};
            $.each(agents, function (i, agent) {
                let type = agent.type || 'Unknown';
                if (!groups[type]) groups[type] = [];
                groups[type].push(agent);
            });

            // 2. 定义 type 排序优先级（LLM > PGM > 其他）
            let typePriority = { 'LLM': 1, 'PGM': 2 };
            let sortedTypes = Object.keys(groups).sort(function (a, b) {
                let pa = typePriority[a] || 99;
                let pb = typePriority[b] || 99;
                if (pa !== pb) return pa - pb;
                return a.localeCompare(b);
            });

            // 3. 渲染分组
            $.each(sortedTypes, function (i, type) {
                // 组内按 id 排序
                groups[type].sort(function (a, b) {
                    return a.id.localeCompare(b.id);
                });

                // 添加分组标题（占一整行）
                $grid.append(createGroupHeader(type, groups[type].length));

                // 添加该组的 cards
                $.each(groups[type], function (j, agent) {
                    $grid.append(createAgentCard(agent));
                });
            });

            // 绑定删除按钮
            $('.delete-btn').off('click').on('click', function () {
                let agentId = $(this).data('id');
                let agentName = $(this).data('name');
                if (confirm(`Sure to delete agent "${agentName}" (ID: ${agentId})?`)) {
                    $.ajax({
                        url: `/agents/api/${agentId}`,
                        type: 'DELETE',
                        success: function () {
                            loadAgents($searchInput.val());
                        },
                        error: function (xhr) {
                            alert('Delete failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
                        }
                    });
                }
            });
        }).fail(function (xhr) {
            alert('Load failed: ' + (xhr.responseJSON?.error || 'Network error'));
            $noResults.removeClass('d-none').find('h4').text('Load error');
        });
    }

    // 搜索输入实时过滤
    $searchInput.on('input', function () {
        loadAgents($(this).val().trim());
    });

    // 页面加载完成立即加载
    loadAgents();
});