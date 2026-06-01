$(document).ready(function () {
    function getTypeBadge(type) {
        if (type === 'LLM') return 'bg-primary';
        if (type === 'PGM') return 'bg-info';
        return 'bg-secondary';
    }

    createEntityListPage({
        $grid: $('#agentGrid'),
        $noResults: $('#noResults'),
        $searchInput: $('#searchInput'),
        $versionsModal: $('#versionsModal'),
        $versionsModalBody: $('#versionsModalBody'),
        $versionsModalLabel: $('#versionsModalLabel'),
        apiListUrl: '/agents/api/list',
        entityLabel: 'agent',
        editUrl: (id) => `/agents/${encodeURIComponent(id)}/edit`,
        copyUrl: (id) => `/agents/api/${encodeURIComponent(id)}/copy`,
        deleteUrl: (id) => `/agents/api/${encodeURIComponent(id)}`,
        versionsUrl: (id) => `/agents/api/${encodeURIComponent(id)}/versions`,
        compareUrl: (id) => `/agents/api/${encodeURIComponent(id)}/compare`,
        groupByField: 'type',
        groupOrder: ['LLM', 'PGM'],
        groupLabels: { LLM: 'LLM', PGM: 'PGM' },
        groupBadges: { LLM: 'bg-primary', PGM: 'bg-info' },
        groupDefaultKey: 'Other',
        renderCardExtra(item, escHtml) {
            const typeText = item.type || 'Unknown';
            const typeBadge = getTypeBadge(item.type);
            const modelHtml = item.model
                ? `<div class="mt-1"><strong>Model:</strong> ${escHtml(item.model)}</div>`
                : '';
            const desc = item.description
                ? `<div class="wf-family-desc mt-1">${escHtml(item.description)}</div>`
                : '';
            return `
                <div class="mt-1">
                    <strong>Type:</strong>
                    <span class="badge ${typeBadge}">${escHtml(typeText)}</span>
                </div>
                ${modelHtml}
                ${desc}`;
        },
    }).init();
});
