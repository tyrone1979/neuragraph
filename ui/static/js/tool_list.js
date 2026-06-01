$(document).ready(function () {
    createEntityListPage({
        $grid: $('#toolGrid'),
        $noResults: $('#noResults'),
        $searchInput: $('#searchInput'),
        $versionsModal: $('#versionsModal'),
        $versionsModalBody: $('#versionsModalBody'),
        $versionsModalLabel: $('#versionsModalLabel'),
        apiListUrl: '/tools/api/list',
        entityLabel: 'tool',
        editUrl: (id) => `/tools/${encodeURIComponent(id)}`,
        copyUrl: (id) => `/tools/api/${encodeURIComponent(id)}/copy`,
        deleteUrl: (id) => `/tools/api/${encodeURIComponent(id)}`,
        versionsUrl: (id) => `/tools/api/${encodeURIComponent(id)}/versions`,
        compareUrl: (id) => `/tools/api/${encodeURIComponent(id)}/compare`,
        renderCardExtra(item, escHtml) {
            const desc = item.description || '';
            return `<div class="wf-family-desc mt-1">${escHtml(desc)}</div>`;
        },
    }).init();
});
