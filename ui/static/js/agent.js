// static/js/runner.js
$(document).ready(function () {
    const $grid = $('#agentGrid');
    const $noResults = $('#noResults');
    const $searchInput = $('#searchInput');

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

            $.each(agents, function (i, agent) {
                // 安全获取 type 和 badge 类
                let typeText = agent.type || 'Unknown';
                let typeBadge = 'bg-secondary'; // 默认灰色
                if (agent.type === 'LLM') typeBadge = 'bg-primary';
                else if (agent.type === 'PGM') typeBadge = 'bg-info';

                // 用 name 作为主标题，ID 作为 code
                let title = agent.name || agent.id || 'Unnamed Agent';

                let modelHtml = '';
                if (agent.model) {
                    modelHtml = `<p class="card-text"><strong>Model:</strong> ${agent.model}</p>`;
                }

                let cardHtml = `
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

                $grid.append(cardHtml);
            });

            // 绑定删除按钮（事件委托，更稳）
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