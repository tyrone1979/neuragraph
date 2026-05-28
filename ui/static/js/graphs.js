$(document).ready(function () {
    const $grid = $('#graphGrid');
    const $noResults = $('#noResults');
    const $searchInput = $('#searchInput');
    let currentGraphs = Array.isArray(graphsData) ? [...graphsData] : [];


    // 加载 Agent 列表
    function loadGraphs(query = '') {
            $grid.empty();
            const q = (query || '').toLowerCase().trim();
            const filtered = currentGraphs.filter((graph) => {
                if (!q) return true;
                return String(graph.name || '').toLowerCase().includes(q) ||
                    String(graph.id || '').toLowerCase().includes(q);
            });

            if (filtered.length === 0) {
                $noResults.removeClass('d-none');
                return;
            }
            $noResults.addClass('d-none');

            $.each(filtered, function (i, graph) {
                let typeBadge = 'bg-secondary'; // 默认灰色
                // 用 name 作为主标题，ID 作为 code
                let title = graph.name || graph.id || 'Unnamed Workflow';
                let cardHtml = `
                <div class="col">
                    <div class="card h-100 shadow-sm">
                        <div class="card-body">
                            <h5 class="card-title">${title}</h5>
                            <p class="card-text">
                                <strong>ID:</strong> <code>${graph.id}</code><br>
                                <strong>Description:</strong> ${graph.description || ""}<br>
                            </p>

                        </div>
                        <div class="card-footer bg-transparent d-flex justify-content-between">
                            <a href="/graph/${graph.id}/edit" class="btn btn-sm btn-outline-primary">Edit</a>
                            <div class="d-flex gap-1">
                                <button class="btn btn-sm btn-outline-secondary copy-btn" data-id="${graph.id}" data-name="${title}">Copy</button>
                                <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${graph.id}" data-name="${title}">Delete</button>
                            </div>
                        </div>
                    </div>
                </div>`;

                $grid.append(cardHtml);
            });


    }
    // 绑定删除按钮（事件委托）
    $grid.off('click', '.delete-btn').on('click', '.delete-btn', function () {
        let graphId = $(this).data('id');
        let graphName = $(this).data('name');
        if (!confirm(`Sure to delete workflow "${graphName}" (ID: ${graphId})?`)) return;
        $.ajax({
            url: `/graph/api/${encodeURIComponent(graphId)}`,
            type: 'DELETE',
            success: function () {
                currentGraphs = currentGraphs.filter(g => g.id !== graphId);
                loadGraphs($searchInput.val());
            },
            error: function (xhr) {
                alert('Delete failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            }
        });
    });

    // 绑定复制按钮（事件委托）
    $grid.off('click', '.copy-btn').on('click', '.copy-btn', function () {
        let graphId = $(this).data('id');
        let graphName = $(this).data('name');
        const suggested = `${graphId}_copy`;
        const newId = (prompt(`Copy workflow "${graphName}"\nNew workflow ID:`, suggested) || '').trim();
        if (!newId) return;
        $.ajax({
            url: `/graph/api/${encodeURIComponent(graphId)}/copy`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ id: newId }),
            success: function (resp) {
                const newGraph = {
                    id: resp.id || newId,
                    name: `${graphName} (copy)`,
                    description: ''
                };
                currentGraphs.unshift(newGraph);
                loadGraphs($searchInput.val());
                window.location.href = `/graph/${encodeURIComponent(newId)}/edit`;
            },
            error: function (xhr) {
                alert('Copy failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            }
        });
    });
    // 搜索输入实时过滤
    $searchInput.on('input', function () {
        loadGraphs($(this).val().trim());
    });

    // 页面加载完成立即加载
    loadGraphs();
});