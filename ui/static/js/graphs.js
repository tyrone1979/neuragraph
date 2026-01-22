$(document).ready(function () {
    const $grid = $('#graphGrid');
    const $noResults = $('#noResults');
    const $searchInput = $('#searchInput');


    // 加载 Agent 列表
    function loadGraphs(query = '') {
            $grid.empty();

            if (graphsData.length === 0) {
                $noResults.removeClass('d-none');
                return;
            }
            $noResults.addClass('d-none');

            $.each(graphsData, function (i, graph) {
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
                            <button class="btn btn-sm btn-outline-danger delete-btn" data-id="${graph.id}" data-name="${title}">Delete</button>
                        </div>
                    </div>
                </div>`;

                $grid.append(cardHtml);
            });


    }
    // 绑定删除按钮（事件委托，更稳）
     $('.delete-btn').off('click').on('click', function () {
                let graphId = $(this).data('id');
                let graphName = $(this).data('name');
                if (confirm(`Sure to delete agent "${graphName}" (ID: ${graphId})?`)) {
                    $.ajax({
                        url: `/graphs/api/${graphId}`,
                        type: 'DELETE',
                        success: function () {
                            loadGraphs($searchInput.val());
                        },
                        error: function (xhr) {
                            alert('Delete failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
                        }
                    });
                }
     });
    // 搜索输入实时过滤
    $searchInput.on('input', function () {
        loadGraphs($(this).val().trim());
    });

    // 页面加载完成立即加载
    loadGraphs();
});